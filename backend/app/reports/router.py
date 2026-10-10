"""
RENTAL OS — Reports Router

Comprehensive analytics & PDF-ready owner statements.

Routes are grouped by purpose and mounted onto a single `/reports` router:
  - `statement.py`   — owner P&L statement + collection trend
  - `receivables.py` — aged receivables + rent roll
  - `books.py`       — books of accounts bundle / CSV export
  - `exports.py`     — PDF statement, KRA eTIMS export, monthly dispatch
"""

from __future__ import annotations

from fastapi import APIRouter

from app.reports.books import router as books_router
from app.reports.exports import router as exports_router
from app.reports.receivables import router as receivables_router
from app.reports.statement import router as statement_router

router = APIRouter(prefix="/reports", tags=["reports"])

router.include_router(statement_router)
router.include_router(receivables_router)
router.include_router(books_router)
router.include_router(exports_router)
