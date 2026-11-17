"""fts_tsvector_gin_trgm

Revision ID: f1a2b3c4d5e6
Revises: e7b9c14a2f01
Create Date: 2026-11-03 20:41:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e7b9c14a2f01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable pg_trgm extension for fuzzy trigram search
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Add stored generated tsvector column using 'simple' dictionary for multilingual/Hinglish text
    op.execute(
        "ALTER TABLE chunks ADD COLUMN IF NOT EXISTS tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('simple', coalesce(content, ''))) STORED;"
    )

    # 3. Create GIN index on stored tsvector
    op.execute("CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin(tsv);")

    # 4. Create GIN trigram index on chunk content for typo tolerance
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_content_trgm_idx ON chunks USING gin(content gin_trgm_ops);"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunks_content_trgm_idx;")
    op.execute("DROP INDEX IF EXISTS chunks_tsv_idx;")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS tsv;")
