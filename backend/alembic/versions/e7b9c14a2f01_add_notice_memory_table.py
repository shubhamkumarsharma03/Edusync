"""add_notice_memory_table

Revision ID: e7b9c14a2f01
Revises: 1735751820e5
Create Date: 2026-10-26 22:15:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7b9c14a2f01"
down_revision: str | Sequence[str] | None = "1735751820e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notice_memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("notice_type", sa.Text(), nullable=False),
        sa.Column("department", sa.Text(), nullable=True),
        sa.Column("target_year", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("target_semester", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("target_branch", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("academic_session", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("notice_serial", sa.Text(), nullable=True),
        sa.Column("title_summary", sa.Text(), nullable=False),
        sa.Column(
            "key_facts",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("content_fingerprint", sa.Text(), nullable=False),
        sa.Column("is_latest", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "superseded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notice_memory.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("supersession_reason", sa.Text(), nullable=True),
        sa.Column(
            "analyzed_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "gemini_model",
            sa.Text(),
            server_default=sa.text("'gemini-2.5-flash'"),
            nullable=False,
        ),
        sa.Column("raw_llm_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.create_index(
        "idx_notice_memory_fingerprint",
        "notice_memory",
        ["content_fingerprint"],
    )
    op.create_index(
        "idx_notice_memory_latest",
        "notice_memory",
        ["is_latest"],
        postgresql_where=sa.text("is_latest = true"),
    )
    op.create_index(
        "idx_notice_memory_dept_type",
        "notice_memory",
        ["department", "notice_type"],
    )


def downgrade() -> None:
    op.drop_index("idx_notice_memory_dept_type", table_name="notice_memory")
    op.drop_index("idx_notice_memory_latest", table_name="notice_memory")
    op.drop_index("idx_notice_memory_fingerprint", table_name="notice_memory")
    op.drop_table("notice_memory")
