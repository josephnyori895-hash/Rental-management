"""
RENTAL OS — Accounting Models

Re-exports from the canonical models in app.models.accounting
plus the extended ChartOfAccount for multi-owner 35-account COA.
"""

from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.accounting import AccountType, JournalEntry  # noqa: F401 — reuse existing
from app.models.base import TimestampMixin, UUIDMixin


class ChartOfAccount(Base, UUIDMixin, TimestampMixin):
    """Extended Chart of Accounts — one set per business, customisable.

    Coexists alongside the legacy `accounts` table for new deployments.
    """

    __tablename__ = "chart_of_accounts"

    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    category: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_system: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chart_of_accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    sort_order: Mapped[int | None] = mapped_column(default=0)

    parent = relationship("ChartOfAccount", remote_side="ChartOfAccount.id", backref="children")
