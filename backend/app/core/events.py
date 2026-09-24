"""
IMANI Business OS

Module:
    Event-Driven Core — Pub/Sub System

Author:
    OpenAI + Your Team

Purpose:
    Lightweight event bus for decoupled module communication.
    Every domain publishes events; other domains subscribe.
    No module ever calls another directly.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from app.core.database import async_session_factory


# ── Event Types ────────────────────────────────────────────────


class EventType(str, Enum):
    """Every event that can occur in the IMANI system."""

    # ── Business Lifecycle ──
    BUSINESS_REGISTERED = "business.registered"
    BUSINESS_UPDATED = "business.updated"
    BUSINESS_INITIALIZED = "business.initialized"
    SUBSCRIPTION_CHANGED = "business.subscription.changed"

    # ── Shifts & Cash Drawer ──
    SHIFT_OPENED = "shift.opened"
    SHIFT_CLOSED = "shift.closed"
    SHIFT_APPROVED = "shift.approved"
    CASH_DRAWER_EVENT = "cash.drawer.event"
    SHIFT_EXPENSE_RECORDED = "shift.expense.recorded"

    # ── Staff ──
    STAFF_CREATED = "staff.created"
    STAFF_UPDATED = "staff.updated"
    STAFF_DELETED = "staff.deleted"
    STAFF_LOGIN = "staff.login"

    # ── Catalog ──
    CATEGORY_CREATED = "catalog.category.created"
    CATEGORY_UPDATED = "catalog.category.updated"
    CATEGORY_DELETED = "catalog.category.deleted"
    PRODUCT_CREATED = "catalog.product.created"
    PRODUCT_UPDATED = "catalog.product.updated"
    PRODUCT_DELETED = "catalog.product.deleted"
    STOCK_ALERT = "catalog.stock.alert"

    # ── Orders / POS ──
    ORDER_CREATED = "pos.order.created"
    ORDER_UPDATED = "pos.order.updated"
    ORDER_COMPLETED = "pos.order.completed"
    ORDER_REFUNDED = "pos.order.refunded"
    ORDER_CANCELLED = "pos.order.cancelled"
    ORDER_ITEM_ADDED = "pos.order.item.added"
    ORDER_ITEM_REMOVED = "pos.order.item.removed"
    ORDER_CONFIRMED = "pos.order.confirmed"
    KITCHEN_TICKET_CREATED = "pos.kitchen.ticket.created"
    KITCHEN_TICKET_READY = "pos.kitchen.ticket.ready"
    TABLE_OCCUPIED = "pos.table.occupied"
    TABLE_FREED = "pos.table.freed"

    # ── Payments ──
    PAYMENT_RECEIVED = "payment.received"
    PAYMENT_REFUNDED = "payment.refunded"

    # ── Receipts ──
    RECEIPT_GENERATED = "receipt.generated"
    Mpesa_STK_SENT = "payment.mpesa.stk.sent"
    Mpesa_CONFIRMED = "payment.mpesa.confirmed"
    Mpesa_FAILED = "payment.mpesa.failed"

    # ── Payments Hub (Outgoing) ──
    BILL_PAID = "payment.bill.paid"
    BILL_PAYMENT_FAILED = "payment.bill.failed"
    BILL_DUE_SOON = "payment.bill.due_soon"
    SUPPLIER_PAID = "payment.supplier.paid"
    TRANSFER_COMPLETED = "payment.transfer.completed"
    SALARY_PAID = "payment.salary.paid"

    # ── Inventory ──
    STOCK_RECEIVED = "inventory.stock.received"
    STOCK_MOVED = "inventory.stock.moved"
    STOCK_ADJUSTED = "inventory.stock.adjusted"
    STOCK_WASTED = "inventory.stock.wasted"
    STOCK_COUNT_COMPLETED = "inventory.stock.count.completed"
    LOW_STOCK_ALERT = "inventory.stock.low"
    PURCHASE_ORDER_CREATED = "inventory.purchase.order.created"
    PURCHASE_ORDER_RECEIVED = "inventory.purchase.order.received"

    # ── Accounting ──
    JOURNAL_ENTRY_POSTED = "accounting.journal.posted"
    LEDGER_UPDATED = "accounting.ledger.updated"
    EXPENSE_RECORDED = "accounting.expense.recorded"
    DAILY_CLOSE = "accounting.daily.close"

    # ── AI ──
    AI_INSIGHT_GENERATED = "ai.insight.generated"
    AI_ANOMALY_DETECTED = "ai.anomaly.detected"
    AI_FORECAST_READY = "ai.forecast.ready"

    # ── Wallet ──
    WALLET_MOVEMENT = "wallet.movement"

    # ── Daily Close ──
    DAILY_CLOSE_STARTED = "daily.close.started"
    DAILY_CLOSE_COMPLETED = "daily.close.completed"

    # ── CCTV ──
    CCTV_EVENT_DETECTED = "cctv.event.detected"
    CCTV_ALERT_TRIGGERED = "cctv.alert.triggered"

    # ── Notifications ──
    NOTIFICATION_SENT = "notification.sent"

    # ── Approvals ──
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_CANCELLED = "approval.cancelled"

    # ── Decision Engine ──
    DECISION_VIEWED = "decision.viewed"
    DECISION_EXECUTED = "decision.executed"
    DECISION_DISMISSED = "decision.dismissed"


# ── Event Payload ──────────────────────────────────────────────


class Event:
    """
    A domain event carrying data and metadata.

    Every event has:
    - event_type: What happened
    - aggregate_id: The primary entity ID (e.g. order_id)
    - business_id: Tenant scope
    - data: Arbitrary payload
    - correlation_id: For tracing across modules
    """

    def __init__(
        self,
        event_type: EventType,
        aggregate_id: str,
        business_id: str,
        data: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.event_id = str(uuid.uuid4())
        self.event_type = event_type
        self.aggregate_id = aggregate_id
        self.business_id = business_id
        self.data = data or {}
        self.correlation_id = correlation_id or self.event_id
        self.user_id = user_id
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "aggregate_id": self.aggregate_id,
            "business_id": self.business_id,
            "data": self.data,
            "correlation_id": self.correlation_id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
        }


# ── Handler Registry ──────────────────────────────────────────

Handler = Callable[[Event], None]
_handler_registry: dict[EventType, list[Handler]] = {}


def subscribe(event_type: EventType, handler: Handler) -> None:
    """Register a handler function for a given event type."""
    if event_type not in _handler_registry:
        _handler_registry[event_type] = []
    _handler_registry[event_type].append(handler)


def publish(event: Event) -> None:
    """
    Publish an event to all registered handlers synchronously.

    In production, this would push to Redis Streams / Kafka.
    For now, it persists to the event log and calls handlers.
    """
    # Persist to event_log. publish() is sync but always invoked within a
    # running asyncio loop in this codebase, so schedule the coroutine on the
    # ACTIVE loop (get_running_loop — never get_event_loop, which can resolve
    # to a stale/cached loop and silently drop the task).
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(_persist_event(event))
    else:
        # No running loop (rare / non-async context) — persist best-effort.
        try:
            asyncio.run(_persist_event(event))
        except RuntimeError:
            pass

    handlers = _handler_registry.get(event.event_type, [])
    for handler in handlers:
        try:
            handler(event)
        except Exception as e:
            print(f"[EVENTS] Handler error for {event.event_type}: {e}")


def publish_async(event: Event) -> None:
    """
    Publish asynchronously via background task.

    The event is persisted immediately; handlers run
    in a separate transaction to avoid blocking the caller.
    """
    _persist_event(event)
    _enqueue_background(event)


# ── Persistence ────────────────────────────────────────────────


async def _persist_event(event: Event) -> None:
    """Write the event to the event_log table."""
    from app.models.event import EventLog

    try:
        async with async_session_factory() as session:
            log_entry = EventLog(
                event_id=str(event.event_id),
                event_type=event.event_type.value,
                aggregate_id=event.aggregate_id,
                business_id=uuid.UUID(event.business_id)
                if event.business_id
                else None,
                correlation_id=event.correlation_id,
                user_id=uuid.UUID(event.user_id) if event.user_id else None,
                data=event.data,
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        print(f"[EVENTS] Persist error: {e}")


def _enqueue_background(event: Event) -> None:
    """
    Queue event for background processing.

    Placeholder for Redis Streams / Celery integration.
    """
    pass


# ── Module Auto-Discovery ──────────────────────────────────────

import importlib
import pkgutil
from pathlib import Path


def _discover_and_register_handlers() -> None:
    """
    Scan all modules in app/ for event handler registration.

    Each module that wants to handle events should define
    a function `register_event_handlers()` that subscribes
    to relevant events.
    """
    handler_modules = [
        "app.inventory.event_handlers",
        "app.accounting.event_handlers",
        "app.analytics.event_handlers",
        "app.audit.service",  # Audit has register_event_handlers
        "app.payments.event_handlers",
        "app.reports.event_handlers",
        "app.notifications.event_handlers",
        "app.ai.event_handlers",
        "app.rules_engine.event_handlers",
        "app.inbox.event_handlers",
        "app.approvals.event_handlers",
        "app.business_setup.event_handlers",
        "app.business_memory.consumer",  # Collection-only mirror of canonical events
    ]

    for module_path in handler_modules:
        try:
            mod = importlib.import_module(module_path)
            if hasattr(mod, "register_event_handlers"):
                mod.register_event_handlers()
        except Exception as e:
            # A single broken handler module must not abort registration of the
            # others (would silently disable accounting/inventory/etc. at boot).
            print(f"[EVENTS] Skipping handler module {module_path}: {e}")


# Called at application startup
def init_event_system() -> None:
    """Initialize the event system: discover and register handlers."""
    _discover_and_register_handlers()
