"""strict_department_linking

Revision ID: 1735751820e5
Revises: c8f1e290a345
Create Date: 2026-09-14 09:07:53.803593

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1735751820e5"
down_revision: str | Sequence[str] | None = "c8f1e290a345"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # documents
    op.add_column("documents", sa.Column("department_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_documents_department_id", "documents", "departments", ["department_id"], ["id"]
    )
    op.drop_column("documents", "department")

    # ingestion_sources
    op.add_column("ingestion_sources", sa.Column("department_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_ingestion_sources_department_id",
        "ingestion_sources",
        "departments",
        ["department_id"],
        ["id"],
    )
    op.drop_column("ingestion_sources", "department")


def downgrade() -> None:
    # ingestion_sources
    op.add_column("ingestion_sources", sa.Column("department", sa.Text(), nullable=True))
    op.drop_constraint(
        "fk_ingestion_sources_department_id", "ingestion_sources", type_="foreignkey"
    )
    op.drop_column("ingestion_sources", "department_id")

    # documents
    op.add_column("documents", sa.Column("department", sa.Text(), nullable=True))
    op.drop_constraint("fk_documents_department_id", "documents", type_="foreignkey")
    op.drop_column("documents", "department_id")
