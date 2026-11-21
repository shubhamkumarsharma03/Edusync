"""expand_database_students_and_telemetry

Revision ID: 1bb0537b608d
Revises: e5f6a7b8c9d0
Create Date: 2026-11-21 10:21:52.459720

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1bb0537b608d"
down_revision: str | Sequence[str] | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to support student accounts, telemetry, and knowledge gaps."""
    # 1. Create students table
    op.create_table(
        "students",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("college_roll_no", sa.String(length=50), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("branch", sa.String(length=100), nullable=False),
        sa.Column("semester", sa.SmallInteger(), nullable=False),
        sa.Column("degree", sa.String(length=50), nullable=False, server_default="B.Tech"),
        sa.Column("admission_year", sa.SmallInteger(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="student"),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("semester BETWEEN 1 AND 8", name="ck_students_semester"),
        sa.CheckConstraint(
            "degree IN ('B.Tech', 'M.Tech', 'MCA', 'MBA')", name="ck_students_degree"
        ),
        sa.CheckConstraint("role IN ('student', 'admin')", name="ck_students_role"),
    )
    op.create_index("ix_students_branch_semester", "students", ["branch", "semester"], unique=False)
    op.create_index(
        "ix_students_roll_no",
        "students",
        [sa.text("UPPER(college_roll_no)")],
        unique=False,
    )
    op.create_index(
        "ix_students_email",
        "students",
        [sa.text("LOWER(email)")],
        unique=False,
    )

    # 2. Update chat_sessions table
    op.add_column(
        "chat_sessions",
        sa.Column("student_uuid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_sessions_student_uuid",
        "chat_sessions",
        "students",
        ["student_uuid"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_chat_sessions_student_uuid", "chat_sessions", ["student_uuid"], unique=False
    )
    op.add_column(
        "chat_sessions",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_index(
        "ix_chat_sessions_lookup",
        "chat_sessions",
        ["student_id", "is_archived", "is_pinned", "updated_at"],
        unique=False,
    )

    # 3. Update queries_log table with telemetry columns
    op.add_column(
        "queries_log",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_queries_log_session_id",
        "queries_log",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column(
        "queries_log",
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_queries_log_student_id",
        "queries_log",
        "students",
        ["student_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("queries_log", sa.Column("raw_question", sa.Text(), nullable=True))
    op.add_column("queries_log", sa.Column("rewritten_question", sa.Text(), nullable=True))
    op.add_column("queries_log", sa.Column("detected_intent", sa.String(length=50), nullable=True))
    op.add_column(
        "queries_log",
        sa.Column("target_department", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "queries_log",
        sa.Column(
            "is_fallback",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("queries_log", sa.Column("retrieval_latency_ms", sa.Integer(), nullable=True))
    op.add_column("queries_log", sa.Column("generation_latency_ms", sa.Integer(), nullable=True))
    op.add_column("queries_log", sa.Column("total_latency_ms", sa.Integer(), nullable=True))
    op.add_column(
        "queries_log",
        sa.Column("chunk_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("queries_log", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("queries_log", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("queries_log", sa.Column("model_used", sa.String(length=50), nullable=True))

    op.create_index("ix_queries_log_session", "queries_log", ["session_id"], unique=False)
    op.create_index("ix_queries_log_student", "queries_log", ["student_id"], unique=False)
    op.create_index(
        "ix_queries_log_fallback",
        "queries_log",
        ["is_fallback", "created_at"],
        unique=False,
    )

    # 4. Create knowledge_gaps table
    op.create_table(
        "knowledge_gaps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column("normalized_topic", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=True),
        sa.Column(
            "query_frequency",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="open",
        ),
        sa.Column(
            "resolved_by_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "first_queried_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "last_queried_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open', 'notice_requested', 'resolved')",
            name="ck_knowledge_gaps_status",
        ),
    )
    op.create_index(
        "ix_knowledge_gaps_freq",
        "knowledge_gaps",
        [sa.text("query_frequency DESC"), sa.text("last_queried_at DESC")],
        unique=False,
    )

    # 5. Create query_feedback table
    op.create_table(
        "query_feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
            primary_key=True,
        ),
        sa.Column(
            "query_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("queries_log.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "student_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("students.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("feedback_type", sa.String(length=10), nullable=False),
        sa.Column("issue_tag", sa.String(length=50), nullable=True),
        sa.Column("student_comment", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=30),
            nullable=False,
            server_default="unreviewed",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("feedback_type IN ('up', 'down')", name="ck_query_feedback_type"),
    )
    op.create_index("ix_query_feedback_query", "query_feedback", ["query_id"], unique=False)
    op.create_index("ix_query_feedback_student", "query_feedback", ["student_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("query_feedback")
    op.drop_table("knowledge_gaps")

    op.drop_index("ix_queries_log_fallback", table_name="queries_log")
    op.drop_index("ix_queries_log_student", table_name="queries_log")
    op.drop_index("ix_queries_log_session", table_name="queries_log")
    op.drop_constraint("fk_queries_log_student_id", "queries_log", type_="foreignkey")
    op.drop_constraint("fk_queries_log_session_id", "queries_log", type_="foreignkey")
    op.drop_column("queries_log", "model_used")
    op.drop_column("queries_log", "completion_tokens")
    op.drop_column("queries_log", "prompt_tokens")
    op.drop_column("queries_log", "chunk_scores")
    op.drop_column("queries_log", "total_latency_ms")
    op.drop_column("queries_log", "generation_latency_ms")
    op.drop_column("queries_log", "retrieval_latency_ms")
    op.drop_column("queries_log", "is_fallback")
    op.drop_column("queries_log", "target_department")
    op.drop_column("queries_log", "detected_intent")
    op.drop_column("queries_log", "rewritten_question")
    op.drop_column("queries_log", "raw_question")
    op.drop_column("queries_log", "student_id")
    op.drop_column("queries_log", "session_id")

    op.drop_index("ix_chat_sessions_lookup", table_name="chat_sessions")
    op.drop_column("chat_sessions", "metadata")
    op.drop_index("ix_chat_sessions_student_uuid", table_name="chat_sessions")
    op.drop_constraint("fk_chat_sessions_student_uuid", "chat_sessions", type_="foreignkey")
    op.drop_column("chat_sessions", "student_uuid")

    op.drop_index("ix_students_email", table_name="students")
    op.drop_index("ix_students_roll_no", table_name="students")
    op.drop_index("ix_students_branch_semester", table_name="students")
    op.drop_table("students")
