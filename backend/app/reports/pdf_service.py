"""
RENTAL OS — PDF Report Generator

Generates professional owner statements and payment receipts using ReportLab.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


def _money(amount: float | Decimal) -> str:
    return f"KES {float(amount):,.2f}"


def _add_style(styles, name, **kwargs):
    if name in styles:
        s = styles[name]
        for k, v in kwargs.items():
            setattr(s, k, v)
    else:
        styles.add(ParagraphStyle(name, **kwargs))


def _style_sheet():
    styles = getSampleStyleSheet()
    _add_style(styles, "Title", fontSize=18, leading=22, textColor=colors.HexColor("#059669"), spaceAfter=4, alignment=TA_LEFT, fontName="Helvetica-Bold")
    _add_style(styles, "SubTitle", fontSize=9, leading=12, textColor=colors.HexColor("#64748b"), spaceAfter=10, fontName="Helvetica")
    _add_style(styles, "Section", fontSize=11, leading=14, textColor=colors.HexColor("#1e293b"), spaceBefore=12, spaceAfter=6, fontName="Helvetica-Bold")
    _add_style(styles, "RowLabel", fontSize=9, leading=12, textColor=colors.HexColor("#475569"), fontName="Helvetica")
    _add_style(styles, "RowValue", fontSize=9, leading=12, textColor=colors.HexColor("#0f172a"), fontName="Helvetica-Bold")
    _add_style(styles, "Footer", fontSize=7, leading=9, textColor=colors.HexColor("#94a3b8"), alignment=TA_CENTER, fontName="Helvetica")
    return styles


def build_owner_statement(
    business_name: str,
    period_from: date,
    period_to: date,
    income: float,
    outstanding: float,
    expenses: float,
    expenses_by_cat: dict[str, float],
    net_profit: float,
    margin: float,
    total_units: int,
    occupied: int,
    vacancy: int,
    occupancy_rate: float,
    active_leases: int,
    payment_count: int,
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20*mm, bottomMargin=15*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )
    styles = _style_sheet()
    elements = []

    # Header
    elements.append(Paragraph("OWNER STATEMENT", styles["Title"]))
    elements.append(Paragraph(
        f"{business_name} &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"{period_from.strftime('%d %b %Y')} — {period_to.strftime('%d %b %Y')}",
        styles["SubTitle"],
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 6*mm))

    # Summary cards
    summary_data = [
        [Paragraph("Income", styles["RowLabel"]),
         Paragraph(_money(income), styles["RowValue"])],
        [Paragraph("Outstanding", styles["RowLabel"]),
         Paragraph(_money(outstanding), styles["RowValue"])],
        [Paragraph("Expenses", styles["RowLabel"]),
         Paragraph(f'<font color="#dc2626">{_money(expenses)}</font>', styles["RowValue"])],
        [Paragraph("<b>Net Profit</b>", styles["RowLabel"]),
         Paragraph(f'<font color="#059669"><b>{_money(net_profit)}</b></font>', styles["RowValue"])],
        [Paragraph("Profit Margin", styles["RowLabel"]),
         Paragraph(f"{margin}%", styles["RowValue"])],
    ]
    t = Table(summary_data, colWidths=[100, 120])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f1f5f9")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 4*mm))

    # Expenses breakdown
    if expenses_by_cat:
        elements.append(Paragraph("Expenses Breakdown", styles["Section"]))
        exp_data = [[Paragraph("Category", styles["RowLabel"]),
                     Paragraph("Amount", styles["RowLabel"])]]
        for cat, amt in sorted(expenses_by_cat.items(), key=lambda x: -x[1]):
            exp_data.append([
                Paragraph(cat.replace("_", " ").title(), styles["RowLabel"]),
                Paragraph(_money(amt), styles["RowValue"]),
            ])
        t = Table(exp_data, colWidths=[150, 100])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f8fafc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 4*mm))

    # Operations
    elements.append(Paragraph("Operations Summary", styles["Section"]))
    ops_data = [
        [Paragraph("Total Units", styles["RowLabel"]),
         Paragraph(str(total_units), styles["RowValue"])],
        [Paragraph("Occupied", styles["RowLabel"]),
         Paragraph(str(occupied), styles["RowValue"])],
        [Paragraph("Vacant", styles["RowLabel"]),
         Paragraph(str(vacancy), styles["RowValue"])],
        [Paragraph("Occupancy Rate", styles["RowLabel"]),
         Paragraph(f"{occupancy_rate}%", styles["RowValue"])],
        [Paragraph("Active Leases", styles["RowLabel"]),
         Paragraph(str(active_leases), styles["RowValue"])],
        [Paragraph("Payments This Period", styles["RowLabel"]),
         Paragraph(str(payment_count), styles["RowValue"])],
    ]
    t = Table(ops_data, colWidths=[120, 80])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10*mm))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    elements.append(Paragraph(
        f"Generated by Rental OS on {date.today().strftime('%d %B %Y')} | "
        "This is a computer-generated statement",
        styles["Footer"],
    ))

    doc.build(elements)
    buf.seek(0)
    return buf


def build_payment_receipt(
    tenant_name: str,
    unit_number: str,
    amount: float,
    method: str,
    receipt: str | None = None,
    paid_at: str | None = None,
    invoice_status: str | None = None,
) -> io.BytesIO:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15*mm, bottomMargin=10*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )
    styles = _style_sheet()
    elements = []

    elements.append(Paragraph("PAYMENT RECEIPT", styles["Title"]))
    elements.append(Paragraph("Rental OS", styles["SubTitle"]))
    elements.append(Spacer(1, 4*mm))

    data = [
        [Paragraph("Tenant", styles["RowLabel"]), Paragraph(tenant_name, styles["RowValue"])],
        [Paragraph("Unit", styles["RowLabel"]), Paragraph(f"House {unit_number}", styles["RowValue"])],
        [Paragraph("Amount", styles["RowLabel"]), Paragraph(_money(amount), styles["RowValue"])],
        [Paragraph("Method", styles["RowLabel"]), Paragraph(method.replace("_", " ").title(), styles["RowValue"])],
    ]
    if receipt:
        data.append([Paragraph("Receipt", styles["RowLabel"]), Paragraph(receipt, styles["RowValue"])])
    if paid_at:
        data.append([Paragraph("Date", styles["RowLabel"]), Paragraph(paid_at, styles["RowValue"])])
    if invoice_status:
        label = "Fully Paid" if invoice_status == "paid" else "Partial"
        data.append([Paragraph("Status", styles["RowLabel"]), Paragraph(label, styles["RowValue"])])

    t = Table(data, colWidths=[80, 200])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#f8fafc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 6*mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1")))
    elements.append(Paragraph(
        f"Generated by Rental OS on {date.today().strftime('%d %B %Y')}",
        styles["Footer"],
    ))

    doc.build(elements)
    buf.seek(0)
    return buf
