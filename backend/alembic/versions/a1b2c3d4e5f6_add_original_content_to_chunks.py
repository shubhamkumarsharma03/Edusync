"""add_original_content_to_chunks

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-11-03 21:08:00.000000

"""

from collections.abc import Sequence
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add column original_content to chunks table
    op.add_column("chunks", sa.Column("original_content", sa.Text(), nullable=True))

    # 2. Backfill existing chunks by stripping leading [Context: ...] or [Notice: ...]
    bind = op.get_bind()
    session = Session(bind=bind)

    rows = session.execute(sa.text("SELECT id, content FROM chunks")).fetchall()
    pattern = re.compile(r"^\[(Context|Notice):[^\]]+\]\s*", re.IGNORECASE)

    for row_id, content in rows:
        if content:
            stripped = pattern.sub("", content).strip()
            # If stripped left nothing or was not prefixed, fallback to content
            orig = stripped if stripped else content
            session.execute(
                sa.text("UPDATE chunks SET original_content = :orig WHERE id = :id"),
                {"orig": orig, "id": row_id},
            )

    session.commit()


def downgrade() -> None:
    op.drop_column("chunks", "original_content")

