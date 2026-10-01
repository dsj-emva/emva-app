"""What Emva keeps in Postgres. Every time stored here comes from the injected clock."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Identity,
    Index,
    String,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    selectinload,
)

from emva_api.ladder import LOST, STAGES_AND_LOST, Stage, StageEvent

if TYPE_CHECKING:
    from emva_api.formatter import Formatted, FormattedLead


class Base(DeclarativeBase):
    pass


class DataSource(enum.StrEnum):
    """Where an advertiser's data comes from; every result is labelled with it."""

    HAND_MADE_TEST = "hand_made_test"
    SIMULATED = "simulated"
    PUBLIC = "public"
    PRIVATE = "private"

    @property
    def label(self) -> str:
        """What every number from it carries, e.g. a slope "on hand-made test data"."""
        return {
            DataSource.HAND_MADE_TEST: "on hand-made test data",
            DataSource.SIMULATED: "on simulated data",
            DataSource.PUBLIC: "on public data",
            DataSource.PRIVATE: "on the advertiser's private export",
        }[self]


class FileKind(enum.StrEnum):
    LEADS = "leads"
    STAGE_HISTORY = "stage-history"


def _values(enumeration: type[enum.StrEnum]) -> list[str]:
    return [member.value for member in enumeration]


class Advertiser(Base):
    __tablename__ = "advertiser"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    data_source: Mapped[DataSource] = mapped_column(
        Enum(DataSource, name="data_source", values_callable=_values)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    files: Mapped[list["UploadedFile"]] = relationship(back_populates="advertiser")
    mapping: Mapped["AdvertiserMapping | None"] = relationship(back_populates="advertiser")
    formatting: Mapped["Formatting | None"] = relationship()


class UploadedFile(Base):
    """A raw file as uploaded; its content lives in object storage under object_key until it is
    formatted, then is deleted and object_key cleared.

    Only the file's shape is kept here (row count, column names); its values, which hold
    personal data, are read from object storage and never stored in Postgres.
    """

    __tablename__ = "uploaded_file"
    __table_args__ = (UniqueConstraint("advertiser_id", "kind"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"))
    kind: Mapped[FileKind] = mapped_column(
        Enum(FileKind, name="file_kind", values_callable=_values)
    )
    file_name: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str | None] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int]
    column_names: Mapped[list[str]] = mapped_column(JSON)
    # What each column's values are like (counts and flags, never values), read on upload;
    # null for a file uploaded before they were kept.
    column_facts: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    advertiser: Mapped[Advertiser] = relationship(back_populates="files")


class AdvertiserMapping(Base):
    """The advertiser's Mapping: a draft until confirmed_at is set, and never changed after."""

    __tablename__ = "mapping"

    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"), primary_key=True)
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    # The CRM stage names last read from the stage-history file, with the file's object key and
    # the column they were read from, so a save that changes neither does not read it again.
    crm_stages_read: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The shape of both files the mapping was confirmed against (their columns and the CRM stage
    # names with counts), so a confirmed mapping reads without the raw files.
    confirmed_against: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    advertiser: Mapped[Advertiser] = relationship(back_populates="mapping")


class Lead(Base):
    """A Lead as the Formatter wrote it: no name; its identifier, email and phone only as
    hashes; and only the inputs the Mapping marks, each kept as its kind."""

    __tablename__ = "lead"
    __table_args__ = (UniqueConstraint("advertiser_id", "identifier_hash"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"))
    # The hash of the lead's identifier in the advertiser's CRM, which is often its email.
    identifier_hash: Mapped[str] = mapped_column(String(64))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    email_hash: Mapped[str | None] = mapped_column(String(64))
    phone_hash: Mapped[str | None] = mapped_column(String(64))
    # False when the phone's country was not found, so its digits as written were hashed.
    phone_country_found: Mapped[bool | None]
    number_inputs: Mapped[dict[str, float | None]] = mapped_column(JSON)
    category_inputs: Mapped[dict[str, str | None]] = mapped_column(JSON)
    stage_events: Mapped[list["LeadStageEvent"]] = relationship(order_by="LeadStageEvent.at")


class LeadStageEvent(Base):
    """A lead reaching a Stage of the Canonical ladder, or being lost, at a time."""

    __tablename__ = "stage_event"
    __table_args__ = (Index("stage_event_lead_id", "lead_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lead.id"))
    stage: Mapped[str] = mapped_column(
        Enum(*(str(value) for value in STAGES_AND_LOST), name="stage_or_lost")
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    deal_value: Mapped[float | None] = mapped_column(Float)


class Formatting(Base):
    """What the Formatter made of the advertiser's files, as the screen summarises it."""

    __tablename__ = "formatting"

    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"), primary_key=True)
    formatted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # The Formatter's Summary: counts of leads by Outcome, and the unreadable rows by reason.
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)


class TrainingRun(Base):
    """One fit of the models on the advertiser's formatted data, together with its Backtest; the
    model itself (its parameters, as JSON) lives in object storage under model_key, and the
    Backtest's results, as JSON, under backtest_key."""

    __tablename__ = "training_run"
    __table_args__ = (Index("training_run_advertiser_id", "advertiser_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Increases with every run recorded, so the latest is known even when two runs share a
    # clock time.
    number: Mapped[int] = mapped_column(BigInteger, Identity(always=True), unique=True)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"))
    trained_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    model_key: Mapped[str] = mapped_column(String(255))
    # Null for a run trained before Backtests were kept.
    backtest_key: Mapped[str | None] = mapped_column(String(255))


def keep_formatted(
    session: Session, advertiser: Advertiser, formatted: "Formatted", at: datetime
) -> None:
    """Add the formatted leads, their stage events and the summary, in bulk; the caller commits."""
    leads: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for lead in formatted.leads:
        lead_id = uuid.uuid4()
        leads.append(
            {
                "id": lead_id,
                "advertiser_id": advertiser.id,
                "identifier_hash": lead.identifier_hash,
                "submitted_at": lead.submitted_at,
                "email_hash": lead.email_hash,
                "phone_hash": lead.phone_hash,
                "phone_country_found": lead.phone_country_found,
                "number_inputs": lead.numbers,
                "category_inputs": lead.categories,
            }
        )
        events += [
            {
                "id": uuid.uuid4(),
                "lead_id": lead_id,
                "stage": str(event.stage),
                "at": event.at,
                "deal_value": event.deal_value,
            }
            for event in lead.stage_events
        ]
    if leads:
        session.execute(insert(Lead), leads)
    if events:
        session.execute(insert(LeadStageEvent), events)
    advertiser.formatting = Formatting(
        formatted_at=at, summary=formatted.summary.model_dump(mode="json")
    )


def formatted_leads(session: Session, advertiser: Advertiser) -> list["FormattedLead"]:
    """The advertiser's formatted leads with their stage events, as the Formatter made them, in
    order of submission."""
    from emva_api.formatter import FormattedLead

    leads = session.scalars(
        select(Lead)
        .where(Lead.advertiser_id == advertiser.id)
        .options(selectinload(Lead.stage_events))
        .order_by(Lead.submitted_at, Lead.identifier_hash)
    )
    return [
        FormattedLead(
            identifier_hash=lead.identifier_hash,
            submitted_at=lead.submitted_at,
            email_hash=lead.email_hash,
            phone_hash=lead.phone_hash,
            phone_country_found=lead.phone_country_found,
            numbers=lead.number_inputs,
            categories=lead.category_inputs,
            stage_events=tuple(
                StageEvent(
                    LOST if event.stage == LOST else Stage(event.stage), event.at, event.deal_value
                )
                for event in lead.stage_events
            ),
        )
        for lead in leads
    ]
