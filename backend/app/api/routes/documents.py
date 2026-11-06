import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.current_user import CurrentUser
from app.config import get_settings
from app.db.session import get_db
from app.models import Document
from app.schemas.common import Page
from app.schemas.document import DocumentListParams, DocumentRead
from app.services import documents as document_service
from app.storage.files import FileStorage, get_storage

router = APIRouter(tags=["documents"])


@router.get("/leads/{lead_id}/documents", response_model=Page[DocumentRead])
def list_documents(
    lead_id: uuid.UUID,
    params: Annotated[DocumentListParams, Query()],
    user: CurrentUser,
    db: Session = Depends(get_db),
) -> Page[DocumentRead]:
    items, total = document_service.list_documents(db, user, lead_id, params)
    return Page(
        items=[DocumentRead.model_validate(d) for d in items],
        total=total,
        limit=params.limit,
        offset=params.offset,
    )


@router.post(
    "/leads/{lead_id}/documents", response_model=DocumentRead, status_code=status.HTTP_201_CREATED
)
def upload_document(
    lead_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    user: CurrentUser,
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> Document:
    return document_service.upload_document(
        db,
        storage,
        user,
        lead_id,
        filename=file.filename,
        content_type=file.content_type,
        file=file.file,
        max_bytes=get_settings().max_upload_bytes,
    )


@router.get("/documents/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    user: CurrentUser,
    db: Session = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> StreamingResponse:
    document = document_service.get_document(db, user, document_id)
    return StreamingResponse(
        storage.open(document.storage_key),
        media_type=document.content_type,
        headers={
            # inline: open in the browser's PDF viewer rather than forcing a download.
            "Content-Disposition": _content_disposition(document.original_filename),
            "Content-Length": str(document.size_bytes),
            # Never guess a different type from the bytes.
            "X-Content-Type-Options": "nosniff",
            # Private legal documents: no shared or on-disk caching.
            "Cache-Control": "private, no-store",
            "Cross-Origin-Resource-Policy": "same-origin",
        },
    )


def _content_disposition(filename: str) -> str:
    # An ASCII-only fallback plus the RFC 5987 UTF-8 form; quoting prevents header injection.
    fallback = "".join(c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename)
    return f"inline; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename, safe='')}"
