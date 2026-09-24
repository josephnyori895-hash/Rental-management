"""
RENTAL OS — Tenant Model

Module:
    Tenant (the person/entity renting a unit). Reuses the membership
    pattern from Klabu's Customer model.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    Boolean,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import SoftDeleteMixin, TimestampMixin, UUIDMixin


class Tenant(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A person renting one or more units."""

    __tablename__ = "tenants"

    business_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    id_number: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    whatsapp_phone: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True,
        comment="WhatsApp number for tenant self-service (BALANCE, PAY, REPORT)",
    )
    mpesa_phone: Mapped[str | None] = mapped_column(
        String(40), nullable=True, index=True,
        comment="M-Pesa number the tenant uses to pay rent (STK push target)",
    )
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emergency_contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    id_document_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    leases = relationship("Lease", back_populates="tenant", lazy="selectin")
