"""Firm-private case notes.

A note belongs permanently to the firm whose staff wrote it (`owner_firm_id`).
Staff see their own firm's notes only while their firm is still assigned the case;
admins see every firm's notes; plaintiffs never see notes.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import CaseNote, LegalCase, User
from app.models.enums import FIRM_STAFF_ROLES, UserRole
from app.schemas.note import NoteListParams
from app.services.audit import record_event
from app.services.errors import ForbiddenError, NotFoundError


def _visible_case(db: Session, user: User, case_id: uuid.UUID) -> LegalCase:
    """The case if the caller may see its notes: staff of the currently assigned firm,
    or an admin. 404 otherwise, so other firms can't tell the case exists."""
    stmt = select(LegalCase).where(LegalCase.id == case_id)
    if user.role in FIRM_STAFF_ROLES:
        stmt = stmt.where(LegalCase.assigned_firm_id == user.firm_id)
    case = db.scalar(stmt)
    if case is None:
        raise NotFoundError("Case not found")
    return case


def create_note(db: Session, user: User, case_id: uuid.UUID, content: str) -> CaseNote:
    # only staff of the assigned firm may add notes
    if user.role not in FIRM_STAFF_ROLES:
        raise ForbiddenError("Only staff of the assigned firm can add notes")

    with db.begin():
        case = _visible_case(db, user, case_id)
        note = CaseNote(
            case_id=case.id,
            owner_firm_id=user.firm_id,  # from the signed-in user, never the client
            author_user_id=user.id,
            content=content,
        )
        db.add(note)
        db.flush()
        # The note text stays out of the audit log; it's firm-private.
        record_event(
            db,
            entity_type="case_note",
            entity_id=note.id,
            action="note.created",
            actor=user,
            new_values={"case_id": str(case.id), "owner_firm_id": str(note.owner_firm_id)},
        )

    return _get_note(db, note.id)


def list_notes(
    db: Session, user: User, case_id: uuid.UUID, params: NoteListParams
) -> tuple[Sequence[CaseNote], int]:
    """A page of the notes the caller may read on a case, newest first, plus the total.

    Filtering happens in SQL, so other firms' notes are never loaded.
    """
    if user.role not in FIRM_STAFF_ROLES and user.role != UserRole.ADMIN:
        raise ForbiddenError("Case notes are only available to firm staff")

    stmt = select(CaseNote).where(CaseNote.case_id == case_id)
    if user.role in FIRM_STAFF_ROLES: # only staff of the assigned firm may see their own notes
        stmt = stmt.where(CaseNote.owner_firm_id == user.firm_id)

    with db.begin():
        _visible_case(db, user, case_id)
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        items = db.scalars(
            stmt.options(joinedload(CaseNote.author), joinedload(CaseNote.owner_firm))
            .order_by(CaseNote.created_at.desc(), CaseNote.id.desc())
            .limit(params.limit)
            .offset(params.offset)
        ).all()
    return items, total


def _get_note(db: Session, note_id: uuid.UUID) -> CaseNote:
    with db.begin():
        return db.scalars(
            select(CaseNote)
            .where(CaseNote.id == note_id)
            .options(joinedload(CaseNote.author), joinedload(CaseNote.owner_firm))
            .execution_options(populate_existing=True)
        ).one()
