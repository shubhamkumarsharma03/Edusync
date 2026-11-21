"""create_chat_sessions_table

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-21 09:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "student_id",
            sa.String(100),
            nullable=False,
            server_default="default_student",
        ),
        sa.Column("title", sa.String(255), nullable=False, server_default="New Chat"),
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "messages",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_sessions_student_id", "chat_sessions", ["student_id"])
    op.create_index(
        "ix_chat_sessions_student_updated",
        "chat_sessions",
        ["student_id", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_student_updated", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_student_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
