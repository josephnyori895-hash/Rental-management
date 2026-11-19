"""
RENTAL OS — In-process Scheduler

Modules:
    Runs both recurring jobs without an external cron: the daily rent-reminder
    sweep and the monthly rent run.

Purpose:
    Reminders existed but only fired when an owner pressed a button, so nothing
    reminded anybody on the day rent fell due. The rent run existed for the
    same reason as a button too, so rent accrued only when someone remembered
    to press it. The free deployment target has no scheduler add-on, which
    leaves the web process itself as the only clock available.

Idempotence:
    `process_due_reminders` skips a tenant already reminded today (it checks
    today's `NotificationLog`), so a restart, an overlapping worker, or a manual
    trigger cannot send a second reminder for the same day.
    `run_rent_for_period` skips a lease already invoiced for any part of the
    month, so the rent run can be repeated — or run on every startup — without
    double-billing a tenant.

Caveat:
    In-process work only runs while the process is awake. A free instance that
    has spun down after idle time misses its window until the next request
    wakes it; the startup catch-up covers the gap for rent (the current month
    is still billed the moment the process comes back), and an external cron
    calling `POST /api/v1/notifications/process-reminders` /
    `POST /api/v1/billing/rent-run` remains the durable answer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.rent_run import month_period, run_rent_for_period
from app.core.config import settings
from app.models.business import Business
from app.notifications.service import process_due_reminders

logger = logging.getLogger(__name__)


def seconds_until_next_run(now: datetime | None = None, hour: int | None = None) -> float:
    """Seconds from `now` until the next sweep at `hour` UTC.

    `hour` is clamped to 0..23 rather than raising: it comes from the
    environment, and a typo there should cost a day's schedule, not the whole
    application's startup.
    """
    moment = now or datetime.now(timezone.utc)
    target_hour = settings.REMINDER_HOUR_UTC if hour is None else hour
    target = moment.replace(
        hour=max(0, min(23, int(target_hour))), minute=0, second=0, microsecond=0
    )
    if target <= moment:
        target += timedelta(days=1)
    return (target - moment).total_seconds()


def seconds_until_next_month_run(
    now: datetime | None = None, hour: int | None = None
) -> float:
    """Seconds from `now` until the next 1st-of-month run at `hour` UTC.

    Same clamping rule as the daily sweep. The `+32 days` step always lands in
    the following month (every month is at least 28 days), so a run that has
    already passed today rolls to the 1st of the next month rather than to a
    day that does not exist in a short month.
    """
    moment = now or datetime.now(timezone.utc)
    target_hour = settings.RENT_RUN_HOUR_UTC if hour is None else hour
    target = moment.replace(
        day=1,
        hour=max(0, min(23, int(target_hour))),
        minute=0,
        second=0,
        microsecond=0,
    )
    if target <= moment:
        target = (target + timedelta(days=32)).replace(day=1)
    return (target - moment).total_seconds()


async def run_reminder_sweep(session: AsyncSession) -> int:
    """Remind every business's due tenants once. Returns messages sent.

    Takes a session so the sweep can be driven by tests and by the scheduler
    against the same session/transaction the caller controls.
    """
    businesses = (
        await session.scalars(select(Business).where(Business.is_active.is_(True)))
    ).all()

    sent = 0
    for business in businesses:
        try:
            sent += await process_due_reminders(session, business.id)
        except Exception:
            # One operator's misconfiguration must not stop every other
            # operator's reminders.
            logger.warning(
                "Rent reminder sweep failed for business %s",
                business.id, exc_info=True,
            )
    return sent


@dataclass
class RentRunSweep:
    """What one scheduled run did, summed across every active business."""

    period_start: date
    period_end: date
    created: int = 0
    skipped: int = 0
    # Businesses the run could not bill. Not an exception: one operator's bad
    # data must not deny every other operator this month's invoices.
    failed: list[UUID] = field(default_factory=list)


async def run_monthly_rent(
    session: AsyncSession, period_start: date | None = None
) -> RentRunSweep:
    """Raise every active business's rent invoices for one calendar month.

    Defaults to the current month on the same clock `run_rent_for_period`
    guards with (`date.today()`), so the scheduler can never ask for a period
    the run itself refuses as not started.
    """
    anchor = period_start or date.today()
    start, end = month_period(anchor.year, anchor.month)
    sweep = RentRunSweep(period_start=start, period_end=end)

    businesses = (
        await session.scalars(select(Business).where(Business.is_active.is_(True)))
    ).all()

    for business in businesses:
        try:
            result = await run_rent_for_period(session, business.id, start, end)
        except Exception:
            logger.warning(
                "Rent run failed for business %s (period %s)",
                business.id, start.strftime("%Y-%m"), exc_info=True,
            )
            sweep.failed.append(business.id)
            # The run commits per business, so a failure may have left the
            # session unusable for the next one.
            await session.rollback()
            continue
        sweep.created += len(result.created)
        sweep.skipped += len(result.skipped)

    return sweep


async def _sweep_once() -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        sent = await run_reminder_sweep(session)
    logger.info("Scheduled rent reminder sweep sent %s reminder(s)", sent)


async def _rent_run_once() -> None:
    from app.core.database import async_session_factory

    async with async_session_factory() as session:
        sweep = await run_monthly_rent(session)
    logger.info(
        "Scheduled rent run for %s created %s invoice(s), skipped %s, failed %s",
        sweep.period_start.strftime("%Y-%m"),
        sweep.created,
        sweep.skipped,
        len(sweep.failed),
    )


async def reminder_loop() -> None:
    """Run once at startup, then daily at `REMINDER_HOUR_UTC`.

    Running at startup matters because a deployment that restarts daily would
    otherwise never reach its window; the per-tenant daily guard makes the
    extra run harmless.
    """
    try:
        await _sweep_once()
    except Exception:
        logger.warning("Startup rent reminder sweep failed", exc_info=True)

    while True:
        await asyncio.sleep(seconds_until_next_run())
        try:
            await _sweep_once()
        except Exception:
            logger.warning("Scheduled rent reminder sweep failed", exc_info=True)


async def rent_run_loop() -> None:
    """Run once at startup, then monthly on the 1st at `RENT_RUN_HOUR_UTC`.

    The startup run is the catch-up: a free instance asleep on the 1st would
    otherwise skip the month entirely, and an already-billed month is a no-op
    thanks to the overlap guard.
    """
    try:
        await _rent_run_once()
    except Exception:
        logger.warning("Startup rent run failed", exc_info=True)

    while True:
        await asyncio.sleep(seconds_until_next_month_run())
        try:
            await _rent_run_once()
        except Exception:
            logger.warning("Scheduled rent run failed", exc_info=True)


def start_scheduler() -> list[asyncio.Task]:
    """Start the in-process loops that configuration has not disabled."""
    tasks: list[asyncio.Task] = []

    if settings.REMINDERS_ENABLED:
        tasks.append(asyncio.create_task(reminder_loop()))
    else:
        logger.info("Rent reminder scheduler disabled (REMINDERS_ENABLED=false)")

    if settings.RENT_RUN_ENABLED:
        tasks.append(asyncio.create_task(rent_run_loop()))
    else:
        logger.info("Monthly rent run disabled (RENT_RUN_ENABLED=false)")

    return tasks
