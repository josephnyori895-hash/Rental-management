"""
RENTAL OS — Documents Router

Upload, list, download, and delete documents.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from app.api.deps import SessionDep, get_current_business
from app.documents.service import (
    delete_document,
    get_document,
    list_documents,
    store_document,
)
from app.models.business import Business
from fastapi.responses import FileResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    file: UploadFile = File(...),
    category: str = Form("other"),
    tenant_id: str | None = Form(None),
    lease_id: str | None = Form(None),
    notes: str | None = Form(None),
):
    """Upload a file. Stores to disk and creates DB record."""
    contents = await file.read()
    tid = uuid.UUID(tenant_id) if tenant_id else None
    lid = uuid.UUID(lease_id) if lease_id else None

    doc = await store_document(
        session=session,
        business_id=business.id,
        file_bytes=contents,
        original_name=file.filename or "unnamed",
        mime_type=file.content_type or "application/octet-stream",
        category=category,
        tenant_id=tid,
        lease_id=lid,
        notes=notes,
    )
    return {
        "id": str(doc.id),
        "original_name": doc.original_name,
        "category": doc.category,
        "file_size": doc.file_size,
        "mime_type": doc.mime_type,
        "created_at": str(doc.created_at),
    }


@router.get("/list")
async def list_uploaded_documents(
    session: SessionDep,
    business: Business = Depends(get_current_business),
    tenant_id: str | None = Query(None),
    category: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
):
    docs = await list_documents(
        session, business.id,
        tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
        category=category,
        limit=limit, offset=offset,
    )
    return {
        "total": len(docs),
        "documents": [
            {
                "id": str(d.id),
                "original_name": d.original_name,
                "category": d.category,
                "mime_type": d.mime_type,
                "file_size": d.file_size,
                "tenant_id": str(d.tenant_id) if d.tenant_id else None,
                "lease_id": str(d.lease_id) if d.lease_id else None,
                "notes": d.notes,
                "created_at": str(d.created_at),
            }
            for d in docs
        ],
    }


@router.get("/{doc_id}/download")
async def download_document(
    doc_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    doc = await get_document(session, uuid.UUID(doc_id))
    if not doc or doc.business_id != business.id:
        raise HTTPException(status_code=404, detail="Document not found")

    path = Path(doc.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        path=path,
        media_type=doc.mime_type,
        filename=doc.original_name,
    )


@router.delete("/{doc_id}")
async def remove_document(
    doc_id: str,
    session: SessionDep,
    business: Business = Depends(get_current_business),
):
    doc = await get_document(session, uuid.UUID(doc_id))
    if not doc or doc.business_id != business.id:
        raise HTTPException(status_code=404, detail="Document not found")
    ok = await delete_document(session, doc.id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to delete document")
    return {"deleted": True}
