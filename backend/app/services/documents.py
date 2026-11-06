import uuid
from collections.abc import Iterator, Sequence
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Document, Lead, User
from app.models.enums import UserRole
from app.schemas.document import DocumentListParams
from app.services.audit import record_event
from app.services.errors import FileTooLargeError, ForbiddenError, InvalidFileError, NotFoundError
from app.services.leads import _lead_scope
from app.storage.files import FileStorage, new_key, read_chunks

PDF_CONTENT_TYPE = "application/pdf"
PDF_SIGNATURE = b"%PDF-"

# Documents follow their lead's access: the owning plaintiff, staff of the firm the
# lead is *currently* assigned to, and admins. A firm that declined the lead (or
# lost it) has no access, because the lead is no longer in its scope.


def _visible_lead(db: Session, user: User, lead_id: uuid.UUID) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.id == lead_id, _lead_scope(user)))
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _clean_filename(name: str | None) -> str:
    """Display name only: drop any path parts and control characters."""
    name = (name or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:255] or "document.pdf"


def _pdf_chunks(file: BinaryIO, max_bytes: int, sizes: list[int]) -> Iterator[bytes]:
    size = 0
    for chunk in read_chunks(file):
        if size == 0 and not chunk.startswith(PDF_SIGNATURE):
            raise InvalidFileError("Only PDF files can be uploaded")
        size += len(chunk)
        if size > max_bytes:
            raise FileTooLargeError(f"File is larger than the {max_bytes // (1024 * 1024)} MB limit")
        yield chunk
    if size == 0:
        raise InvalidFileError("The file is empty")
    sizes.append(size)


def upload_document(
    db: Session,
    storage: FileStorage,
    user: User,
    lead_id: uuid.UUID,
    *,
    filename: str | None,
    content_type: str | None,
    file: BinaryIO,
    max_bytes: int,
) -> Document:
    # store pdf + write metadata, as one transaction
    # In production we would prob wanna switch this out for smth like s3
    key = new_key()
    try:
        with db.begin():
            lead = db.scalar(
                select(Lead).where(Lead.id == lead_id, _lead_scope(user)).with_for_update(read=True)
            )
            if lead is None:
                raise NotFoundError("Lead not found")
            if user.role == UserRole.ADMIN:
                raise ForbiddenError("Admins can view documents but not upload them")
            if content_type != PDF_CONTENT_TYPE:
                raise InvalidFileError("Only PDF files can be uploaded")

            sizes: list[int] = []
            storage.save(key, _pdf_chunks(file, max_bytes, sizes))

            document = Document(
                lead_id=lead.id,
                uploaded_by_user_id=user.id,
                storage_key=key,
                original_filename=_clean_filename(filename),
                content_type=PDF_CONTENT_TYPE,
                size_bytes=sizes[0],
            )
            db.add(document)
            db.flush()
            record_event(
                db,
                entity_type="document",
                entity_id=document.id,
                action="document.uploaded",
                actor=user,
                new_values={
                    "lead_id": str(lead.id),
                    "original_filename": document.original_filename,
                    "size_bytes": document.size_bytes,
                },
            )
    except BaseException:
        storage.delete(key)  # fine even if nothing ends up getting written
        raise

    return get_document(db, user, document.id)


def list_documents(
    db: Session, user: User, lead_id: uuid.UUID, params: DocumentListParams
) -> tuple[Sequence[Document], int]:
    """A page of a visible lead's documents, newest first, plus the total count."""
    stmt = select(Document).where(Document.lead_id == lead_id)
    with db.begin():
        _visible_lead(db, user, lead_id)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(
            stmt.options(joinedload(Document.uploaded_by))
            .order_by(Document.created_at.desc(), Document.id.desc())
            .limit(params.limit)
            .offset(params.offset)
        ).all()
    return items, total


def get_document(db: Session, user: User, document_id: uuid.UUID) -> Document:
    """A document whose lead the caller can see (404 otherwise, including for old firms)."""
    with db.begin():
        document = db.scalar(
            select(Document)
            .join(Lead, Lead.id == Document.lead_id)
            .where(Document.id == document_id, _lead_scope(user))
            .options(joinedload(Document.uploaded_by))
        )
    if document is None:
        raise NotFoundError("Document not found")
    return document
