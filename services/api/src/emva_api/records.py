"""What Emva keeps in Postgres. Every time stored here comes from the injected clock."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


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


class UploadedFile(Base):
    """A raw file as uploaded; its content lives in object storage under object_key.

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
    object_key: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int]
    column_names: Mapped[list[str]] = mapped_column(JSON)
    advertiser: Mapped[Advertiser] = relationship(back_populates="files")
