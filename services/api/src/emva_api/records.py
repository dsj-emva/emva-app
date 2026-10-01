"""What Emva keeps in Postgres. Every time stored here comes from the injected clock."""

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from emva_api.ladder import STAGES_AND_LOST


class Base(DeclarativeBase):
    pass


class DataSource(enum.StrEnum):
    """Where an advertiser's data comes from; every result is labelled with it."""

    HAND_MADE_TEST = "hand_made_test"
    SIMULATED = "simulated"
    PUBLIC = "public"
    PRIVATE = "private"


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
    """A Lead as the Formatter wrote it: no name, email and phone only as hashes, and only the
    inputs the Mapping marks."""

    __tablename__ = "lead"
    __table_args__ = (UniqueConstraint("advertiser_id", "identifier"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    advertiser_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("advertiser.id"))
    # The lead's identifier in the advertiser's CRM.
    identifier: Mapped[str] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    email_hash: Mapped[str | None] = mapped_column(String(64))
    phone_hash: Mapped[str | None] = mapped_column(String(64))
    inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
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
    # The counts of leads by Outcome, and every unreadable row with its reason.
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
