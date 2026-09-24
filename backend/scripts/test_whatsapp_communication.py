"""
RENTAL OS — WhatsApp Communication & Integration Test Suite

Tests full two-way WhatsApp communication flows for Caretakers & Tenants:
1. Outbound Tenant WhatsApp Notifications (Rent Reminder, Payment Receipt, Balance)
2. Outbound Caretaker WhatsApp Alerts (Payment Alert, Ticket Alert, Unpaid Alert, Move-in Alert)
3. Inbound Tenant Webhook Commands (BALANCE, HELP, REPORT <issue>, RECEIPT)
4. Inbound Caretaker Webhook Commands (STATUS, COLLECTIONS)
5. Notification Log Audit & Verification
"""

import sys
import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.business import Business, User, UserRole
from app.models.property import Property, Unit, PropertyType, UnitType, UnitStatus
from app.models.tenant import Tenant
from app.models.lease import Lease, LeaseStatus
from app.models.billing import Invoice, InvoiceStatus, InvoiceType, Payment, PaymentMethod
from app.models.maintenance import MaintenanceTicket, TicketStatus, TicketPriority
from app.notifications.models import NotificationLog
from app.notifications.service import (
    send_notification,
    send_wa_balance,
    send_wa_payment_receipt,
    notify_caretaker_payment,
    notify_caretaker_ticket,
    notify_caretaker_unpaid,
    notify_caretaker_move_in,
)
from app.notifications.inbound import parse_and_handle


class WhatsAppTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def assert_true(self, condition: bool, name: str, details: str = ""):
        if condition:
            self.passed += 1
            print(f"  ✅ [PASS] {name}")
            if details:
                print(f"      └─ {details}")
        else:
            self.failed += 1
            print(f"  ❌ [FAIL] {name}")
            if details:
                print(f"      └─ Error: {details}")
        self.tests.append((name, condition, details))


async def run_whatsapp_communication_tests():
    print("========================================================================")
    print("📱 RENTAL OS — WHATSAPP COMMUNICATION TEST SUITE")
    print("   Testing Caretaker & Tenant Two-Way Messaging Logic")
    print("========================================================================\n")

    t = WhatsAppTester()
    suffix = uuid.uuid4().hex[:6]
    # Use unique phone numbers to avoid conflicts with previous test runs
    phone_suffix = suffix[:4]  # e.g. "a3f2" → numeric via hash
    phone_num = str(abs(hash(suffix)) % 9000000 + 1000000)  # 7 digits
    tenant_phone = f"2547{phone_num[:7]}"
    caretaker_phone = f"2548{phone_num[:7]}"
    owner_phone = f"2549{phone_num[:7]}"

    # ── SETUP ────────────────────────────────────────────────────────────────
    print("--- 0. Setting up test fixtures ---")
    owner_id = uuid.uuid4()
    biz_id = uuid.uuid4()

    async with async_session_factory() as s:
        biz = Business(
            id=biz_id,
            name=f"WhatsApp Test Biz {suffix}",
            slug=f"wa-biz-{suffix}",
            owner_id=owner_id,
        )
        s.add(biz)
        await s.flush()

        owner = User(
            id=owner_id,
            business_id=biz_id,
            email=f"owner-{suffix}@rental.os",
            password_hash="hashed_pass_xyz",
            full_name="Alice Owner",
            phone=owner_phone,
            role=UserRole.OWNER.value,
            is_active=True,
        )
        caretaker = User(
            business_id=biz_id,
            email=f"caretaker-{suffix}@rental.os",
            password_hash="hashed_pass_xyz",
            full_name="Bob Caretaker",
            phone=caretaker_phone,
            role=UserRole.AGENT.value,
            is_active=True,
        )
        s.add_all([owner, caretaker])
        await s.flush()

        prop = Property(
            business_id=biz.id,
            name=f"Sunshine Hostel {suffix}",
            property_type=PropertyType.HOSTEL.value,
            address="123 University Way",
        )
        s.add(prop)
        await s.flush()

        unit = Unit(
            business_id=biz.id,
            property_id=prop.id,
            unit_number="B-204",
            unit_type=UnitType.ROOM.value,
            status=UnitStatus.OCCUPIED.value,
            monthly_rent=7500.00,
        )
        s.add(unit)
        await s.flush()

        tenant = Tenant(
            business_id=biz.id,
            full_name="Charlie Tenant",
            phone=tenant_phone,
            whatsapp_phone=tenant_phone,
            email=f"charlie-{suffix}@test.com",
        )
        s.add(tenant)
        await s.flush()

        lease = Lease(
            business_id=biz.id,
            property_id=prop.id,
            unit_id=unit.id,
            tenant_id=tenant.id,
            start_date=date.today() - timedelta(days=60),
            rent_amount=7500.00,
            status=LeaseStatus.ACTIVE.value,
        )
        s.add(lease)
        await s.flush()

        unit.current_lease_id = lease.id

        invoice = Invoice(
            business_id=biz.id,
            lease_id=lease.id,
            property_id=prop.id,
            unit_id=unit.id,
            tenant_id=tenant.id,
            invoice_type=InvoiceType.RENT.value,
            period_start=date.today().replace(day=1),
            period_end=date.today().replace(day=28),
            due_date=date.today(),
            amount=7500.00,
            paid_amount=0.00,
            balance=7500.00,
            status=InvoiceStatus.PENDING.value,
        )
        s.add(invoice)
        await s.commit()

        # Cache IDs we'll need across sessions
        biz_id = biz.id
        tenant_id = tenant.id
        caretaker_id = caretaker.id
        invoice_id = invoice.id
        unit_id = unit.id
        # tenant_phone and caretaker_phone already set as unique variables above

    print(f"  ✅ Fixtures created (biz: {str(biz_id)[:8]}..., tenant: {str(tenant_id)[:8]}...)\n")

    # ── TEST GROUP 1: Outbound Tenant WhatsApp Messages ───────────────────────
    print("--- 1. Testing Outbound Tenant WhatsApp Notifications ---")
    async with async_session_factory() as s:
        # A) Generic rent reminder
        res1 = await send_notification(
            session=s,
            business_id=biz_id,
            tenant_id=tenant_id,
            channel="whatsapp",
            recipient=tenant_phone,
            template_name="rent_reminder",
            body="🔔 RENT REMINDER — Charlie Tenant\nHouse B-204\nDue: KES 7,500\nReply PAY to pay now",
        )
        t.assert_true(
            res1 is not None and res1.status in ("simulated", "sent"),
            "Outbound Tenant Rent Reminder WhatsApp",
            f"Status: {res1.status if res1 else 'None'}, ID: {res1.id if res1 else 'None'}",
        )

        # B) Balance notification — takes tenant ORM object
        tenant_obj = await s.get(Tenant, tenant_id)
        res2 = await send_wa_balance(
            session=s,
            business_id=biz_id,
            tenant=tenant_obj,
            balance=7500.00,
            due_date=str(date.today()),
        )
        t.assert_true(
            res2 is not None and res2.status in ("simulated", "sent"),
            "Outbound Tenant Balance WhatsApp",
            f"Status: {res2.status if res2 else 'None'}",
        )

        # C) Payment receipt — takes Payment ORM object + tenant ORM object
        payment = Payment(
            business_id=biz_id,
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            amount=7500.00,
            method=PaymentMethod.MPESA.value,
            reference="QWX9876543",
            status="completed",
        )
        s.add(payment)
        await s.flush()

        res3 = await send_wa_payment_receipt(
            session=s,
            payment=payment,
            tenant=tenant_obj,
            unit_number="B-204",
            invoice_status="paid",
        )
        t.assert_true(
            res3 is not None and res3.status in ("simulated", "sent"),
            "Outbound Tenant Payment Receipt WhatsApp",
            f"Status: {res3.status if res3 else 'None'}, Ref: QWX9876543",
        )
        await s.commit()

    # ── TEST GROUP 2: Outbound Caretaker WhatsApp Alerts ────────────────────
    print("\n--- 2. Testing Outbound Caretaker WhatsApp Alerts ---")
    async with async_session_factory() as s:
        # A) Caretaker Payment Alert
        # notify_caretaker_payment(session, business_id, caretaker_phone, tenant_name, unit_number, amount, method)
        res4 = await notify_caretaker_payment(
            session=s,
            business_id=biz_id,
            caretaker_phone=caretaker_phone,
            tenant_name="Charlie Tenant",
            unit_number="B-204",
            amount=7500.00,
            method="mpesa",
        )
        t.assert_true(
            res4 is not None and res4.status in ("simulated", "sent"),
            "Outbound Caretaker Payment Alert WhatsApp",
            f"Recipient: {caretaker_phone}",
        )

        # B) Caretaker Maintenance Ticket Alert
        # notify_caretaker_ticket(session, business_id, caretaker_phone, tenant_name, unit_number, issue, ticket_id)
        fake_ticket_id = str(uuid.uuid4())[:8]
        res5 = await notify_caretaker_ticket(
            session=s,
            business_id=biz_id,
            caretaker_phone=caretaker_phone,
            tenant_name="Charlie Tenant",
            unit_number="B-204",
            issue="Leaking water pipe under sink",
            ticket_id=fake_ticket_id,
        )
        t.assert_true(
            res5 is not None and res5.status in ("simulated", "sent"),
            "Outbound Caretaker Ticket Alert WhatsApp",
            f"Ticket: #{fake_ticket_id}",
        )

        # C) Caretaker Unpaid Alert
        # notify_caretaker_unpaid(session, business_id, caretaker_phone, tenant_name, unit_number, amount, days_overdue)
        res6 = await notify_caretaker_unpaid(
            session=s,
            business_id=biz_id,
            caretaker_phone=caretaker_phone,
            tenant_name="Charlie Tenant",
            unit_number="B-204",
            amount=7500.00,
            days_overdue=5,
        )
        t.assert_true(
            res6 is not None and res6.status in ("simulated", "sent"),
            "Outbound Caretaker Unpaid Alert WhatsApp",
            f"Amount: KES 7,500 | Days overdue: 5",
        )

        # D) Caretaker Move-In Alert
        # notify_caretaker_move_in(session, business_id, caretaker_phone, tenant_name, unit_number, date)
        res7 = await notify_caretaker_move_in(
            session=s,
            business_id=biz_id,
            caretaker_phone=caretaker_phone,
            tenant_name="Charlie Tenant",
            unit_number="B-204",
            date=str(date.today()),
        )
        t.assert_true(
            res7 is not None and res7.status in ("simulated", "sent"),
            "Outbound Caretaker Move-In Alert WhatsApp",
            f"Date: {date.today()}",
        )
        await s.commit()

    # ── TEST GROUP 3: Inbound Tenant WhatsApp Webhook Commands ──────────────
    print("\n--- 3. Testing Inbound Tenant WhatsApp Webhook Commands ---")
    async with async_session_factory() as s:
        # A) Tenant BALANCE Command
        reply_bal = await parse_and_handle(s, tenant_phone, "BALANCE")
        t.assert_true(
            reply_bal is not None and "KES" in reply_bal.get("message", ""),
            "Inbound Tenant Command: 'BALANCE'",
            f"Reply: {reply_bal.get('message', '')[:70]}..." if reply_bal else "No reply",
        )

        # B) Tenant HELP Command
        reply_help = await parse_and_handle(s, tenant_phone, "HELP")
        t.assert_true(
            reply_help is not None and "BALANCE" in reply_help.get("message", ""),
            "Inbound Tenant Command: 'HELP'",
            f"Reply: {reply_help.get('message', '')[:70]}..." if reply_help else "No reply",
        )

        # C) Tenant REPORT Command
        reply_report = await parse_and_handle(s, tenant_phone, "REPORT shower head leaking water")
        t.assert_true(
            reply_report is not None and (
                "ticket" in reply_report.get("message", "").lower()
                or "report" in reply_report.get("message", "").lower()
                or "maintenance" in reply_report.get("message", "").lower()
                or "received" in reply_report.get("message", "").lower()
            ),
            "Inbound Tenant Command: 'REPORT <issue>'",
            f"Reply: {reply_report.get('message', '')[:70]}..." if reply_report else "No reply",
        )

        # D) Verify Maintenance Ticket was created in the DB
        ticket = await s.scalar(
            select(MaintenanceTicket).where(MaintenanceTicket.tenant_id == tenant_id).limit(1)
        )
        t.assert_true(
            ticket is not None and "shower" in (ticket.description or "").lower(),
            "Database Check: Maintenance Ticket Created via WhatsApp REPORT",
            f"Ticket ID: {ticket.id if ticket else 'None'}, Desc: {ticket.description[:40] if ticket else ''}",
        )
        await s.commit()

    # ── TEST GROUP 4: Inbound Caretaker WhatsApp Webhook Commands ─────────────
    print("\n--- 4. Testing Inbound Caretaker WhatsApp Webhook Commands ---")
    async with async_session_factory() as s:
        # A) Caretaker STATUS Command
        reply_status = await parse_and_handle(s, caretaker_phone, "STATUS")
        t.assert_true(
            reply_status is not None and reply_status.get("message"),
            "Inbound Caretaker Command: 'STATUS'",
            f"Reply: {reply_status.get('message', '')[:70]}..." if reply_status else "No reply",
        )

        # B) Caretaker COLLECTIONS Command
        reply_col = await parse_and_handle(s, caretaker_phone, "COLLECTIONS")
        t.assert_true(
            reply_col is not None and reply_col.get("message"),
            "Inbound Caretaker Command: 'COLLECTIONS'",
            f"Reply: {reply_col.get('message', '')[:70]}..." if reply_col else "No reply",
        )
        await s.commit()

    # ── TEST GROUP 5: Audit Notification Logs ──────────────────────────────────
    print("\n--- 5. Auditing Notification Log Integrity ---")
    async with async_session_factory() as s:
        logs = (await s.scalars(
            select(NotificationLog).where(NotificationLog.business_id == biz_id)
        )).all()
        t.assert_true(
            len(logs) >= 5,
            "Notification Audit Trail Verified",
            f"Total WhatsApp notifications logged for this test business: {len(logs)}",
        )
        for log in logs:
            print(f"      📋 [{log.channel.upper()}] {log.template_name} → {log.recipient} [{log.status}]")

    print("\n========================================================================")
    print(f"📊 SUMMARY: {t.passed} PASSED, {t.failed} FAILED across {len(t.tests)} Tests")
    print("========================================================================")

    if t.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_whatsapp_communication_tests())
