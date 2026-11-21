"""allow_archived_status_in_documents

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-11-21 09:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop existing check constraint and replace with one that includes 'archived'
    op.drop_constraint("documents_status_check", "documents", type_="check")
    op.create_check_constraint(
        "documents_status_check",
        "documents",
        "status IN ('fresh', 'stale', 'conflicted', 'pending', 'archived')",
    )


def downgrade() -> None:
    op.drop_constraint("documents_status_check", "documents", type_="check")
    op.create_check_constraint(
        "documents_status_check",
        "documents",
        "status IN ('fresh', 'stale', 'conflicted', 'pending')",
    )
