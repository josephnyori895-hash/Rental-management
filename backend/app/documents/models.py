"""
RENTAL OS — Document Model

Stores metadata for uploaded files (leases, IDs, receipts, etc.).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class Document(Base, UUIDMixin, TimestampMixin):
    """A file uploaded to the system."""

    __tablename__ = "documents"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    lease_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    category: Mapped[str] = mapped_column(
        String(30), nullable=False, default="other",
        comment="lease_agreement | id_document | receipt | invoice | property_photo | other"
    )
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
