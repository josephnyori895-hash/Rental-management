"""
RENTAL OS — Document Service

Handles file storage and retrieval.
"""

from __future__ import annotations

import uuid
import os
import shutil
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.documents.models import Document


def _storage_path() -> Path:
    path = settings.STORAGE_LOCAL_PATH / "documents"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def store_document(
    session: AsyncSession,
    business_id: uuid.UUID,
    file_bytes: bytes,
    original_name: str,
    mime_type: str,
    category: str = "other",
    tenant_id: uuid.UUID | None = None,
    lease_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> Document:
    """Save a file to disk and create a Document record."""
    ext = Path(original_name).suffix or ""
    stored_name = f"{uuid.uuid4().hex}{ext}"
    date_prefix = datetime.now().strftime("%Y/%m")
    rel_path = f"{date_prefix}/{stored_name}"
    abs_path = _storage_path() / date_prefix
    abs_path.mkdir(parents=True, exist_ok=True)

    file_path = abs_path / stored_name
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    doc = Document(
        business_id=business_id,
        tenant_id=tenant_id,
        lease_id=lease_id,
        category=category,
        original_name=original_name,
        stored_name=stored_name,
        mime_type=mime_type,
        file_size=len(file_bytes),
        file_path=str(file_path),
        notes=notes,
    )
    session.add(doc)
    await session.commit()
    return doc


async def get_document(session: AsyncSession, doc_id: uuid.UUID) -> Document | None:
    return await session.get(Document, doc_id)


async def list_documents(
    session: AsyncSession,
    business_id: uuid.UUID,
    tenant_id: uuid.UUID | None = None,
    category: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Document]:
    q = select(Document).where(Document.business_id == business_id)
    if tenant_id:
        q = q.where(Document.tenant_id == tenant_id)
    if category:
        q = q.where(Document.category == category)
    q = q.order_by(Document.created_at.desc()).offset(offset).limit(limit)
    return (await session.scalars(q)).all()


async def delete_document(session: AsyncSession, doc_id: uuid.UUID) -> bool:
    doc = await session.get(Document, doc_id)
    if not doc:
        return False
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    await session.delete(doc)
    await session.commit()
    return True
