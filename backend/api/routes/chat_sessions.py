import logging
import uuid
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth_utils import get_optional_student
from db.session import get_db
from models.chat_session import ChatSession
from models.student import Student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat/sessions", tags=["Chat Sessions"])


class SessionCreateRequest(BaseModel):
    student_id: str = Field(default="student_guest", description="Student account identifier")
    title: str = Field(default="New Chat", description="Initial session title")
    messages: list = Field(default_factory=list, description="Initial conversation messages")
    metadata: dict = Field(default_factory=dict, description="Session metadata")


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    messages: list | None = None
    metadata: dict | None = None


class SessionSummary(BaseModel):
    id: UUID
    student_id: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: str
    updated_at: str
    message_count: int
    last_message_preview: str | None = None


class SessionDetail(BaseModel):
    id: UUID
    student_id: str
    title: str
    is_pinned: bool
    is_archived: bool
    created_at: str
    updated_at: str
    messages: list
    metadata: dict = Field(default_factory=dict)


def _format_summary(s: ChatSession) -> SessionSummary:
    msgs = s.messages or []
    last_msg = msgs[-1].get("text") if msgs and isinstance(msgs[-1], dict) else None
    now_iso = datetime.now(UTC).isoformat()
    return SessionSummary(
        id=s.id or uuid.uuid4(),
        student_id=s.student_id,
        title=s.title,
        is_pinned=s.is_pinned,
        is_archived=s.is_archived,
        created_at=s.created_at.isoformat() if s.created_at else now_iso,
        updated_at=s.updated_at.isoformat() if s.updated_at else now_iso,
        message_count=len(msgs),
        last_message_preview=last_msg[:80] if last_msg else None,
    )


def _format_detail(s: ChatSession) -> SessionDetail:
    now_iso = datetime.now(UTC).isoformat()
    return SessionDetail(
        id=s.id or uuid.uuid4(),
        student_id=s.student_id,
        title=s.title,
        is_pinned=s.is_pinned,
        is_archived=s.is_archived,
        created_at=s.created_at.isoformat() if s.created_at else now_iso,
        updated_at=s.updated_at.isoformat() if s.updated_at else now_iso,
        messages=s.messages or [],
        metadata=s.metadata_ if hasattr(s, "metadata_") and s.metadata_ else {},
    )


@router.get("", response_model=list[SessionSummary])
async def list_sessions(
    student_id: str = Query("student_guest", description="Student account identifier"),
    is_archived: bool | None = Query(None, description="Filter active vs archived chats"),
    current_student: Student | None = Depends(get_optional_student),
    session: AsyncSession = Depends(get_db),
) -> list[SessionSummary]:
    """Retrieve chat sessions for a student, ordered by pinned first, then recency."""
    stmt = select(ChatSession).order_by(desc(ChatSession.is_pinned), desc(ChatSession.updated_at))

    if is_archived is not None:
        stmt = stmt.where(ChatSession.is_archived == is_archived)

    if current_student:
        stmt = stmt.where(
            or_(
                ChatSession.student_uuid == current_student.id,
                ChatSession.student_id == current_student.college_roll_no,
            )
        )
    else:
        stmt = stmt.where(ChatSession.student_id == student_id)

    result = await session.execute(stmt)
    sessions = result.scalars().all()
    return [_format_summary(s) for s in sessions]


@router.post("", response_model=SessionDetail)
async def create_session(
    payload: SessionCreateRequest,
    current_student: Student | None = Depends(get_optional_student),
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Create a new conversational session for a student."""
    resolved_student_id = (
        current_student.college_roll_no
        if current_student
        else (payload.student_id.strip() or "student_guest")
    )
    resolved_uuid = current_student.id if current_student else None

    new_session = ChatSession(
        id=uuid.uuid4(),
        student_id=resolved_student_id,
        student_uuid=resolved_uuid,
        title=payload.title.strip() or "New Chat",
        is_pinned=False,
        is_archived=False,
        messages=payload.messages,
        metadata_=payload.metadata,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(new_session)
    await session.commit()
    await session.refresh(new_session)
    return _format_detail(new_session)


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Retrieve full chat session including message transcript."""
    s = await session.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return _format_detail(s)


@router.patch("/{session_id}", response_model=SessionDetail)
async def update_session(
    session_id: UUID,
    payload: SessionUpdateRequest,
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Update title, pinned/archived flags, or append messages to a session."""
    s = await session.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Chat session not found")

    if payload.title is not None:
        s.title = payload.title.strip() or s.title
    if payload.is_pinned is not None:
        s.is_pinned = payload.is_pinned
    if payload.is_archived is not None:
        s.is_archived = payload.is_archived
    if payload.metadata is not None:
        s.metadata_ = payload.metadata
    if payload.messages is not None:
        s.messages = payload.messages
        # Auto-title session from first user message if still default title
        if s.title in ("New Chat", "Untitled Chat") and s.messages:
            first_user = next(
                (
                    m.get("text", "")
                    for m in s.messages
                    if isinstance(m, dict) and m.get("sender") == "user"
                ),
                None,
            )
            if first_user:
                cleaned = first_user.strip().split("\n")[0]
                s.title = cleaned[:45] + ("..." if len(cleaned) > 45 else "")

    await session.commit()
    await session.refresh(s)
    return _format_detail(s)


@router.delete("/{session_id}")
async def delete_session(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Permanently delete a chat session."""
    s = await session.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Chat session not found")

    await session.delete(s)
    await session.commit()
    return {"status": "success", "session_id": str(session_id)}


@router.post("/{session_id}/pin", response_model=SessionDetail)
async def toggle_pin(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Toggle the pinned state of a session."""
    s = await session.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Chat session not found")

    s.is_pinned = not s.is_pinned
    await session.commit()
    await session.refresh(s)
    return _format_detail(s)


@router.post("/{session_id}/archive", response_model=SessionDetail)
async def toggle_archive(
    session_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> SessionDetail:
    """Toggle the archived state of a session."""
    s = await session.get(ChatSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail="Chat session not found")

    s.is_archived = not s.is_archived
    # Unpin if archiving
    if s.is_archived:
        s.is_pinned = False

    await session.commit()
    await session.refresh(s)
    return _format_detail(s)
