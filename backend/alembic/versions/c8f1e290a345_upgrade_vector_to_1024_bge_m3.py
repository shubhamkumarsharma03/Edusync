"""upgrade_vector_to_1024_bge_m3

Revision ID: c8f1e290a345
Revises: 44b082d3ca97
Create Date: 2026-09-13 12:10:00.000000

"""

from collections.abc import Sequence

import pgvector.sqlalchemy.vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8f1e290a345"
down_revision: str | Sequence[str] | None = "44b082d3ca97"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade chunks.embedding column to 1024 dimensions for BAAI/bge-m3."""
    # 1. Drop old 384-dim index
    op.drop_index("chunks_embedding_idx", table_name="chunks")

    # 2. Reset existing 384-dim embeddings to null to prevent dimension mismatch
    op.execute("UPDATE chunks SET embedding = NULL WHERE embedding IS NOT NULL")

    # 3. Alter column to vector(1024)
    op.alter_column(
        "chunks",
        "embedding",
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=1024),
        existing_nullable=True,
    )

    # 4. Create new HNSW index for vector_cosine_ops on 1024 dimensions
    op.create_index(
        "chunks_embedding_idx",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Downgrade chunks.embedding column back to 384 dimensions."""
    op.drop_index("chunks_embedding_idx", table_name="chunks")
    op.execute("UPDATE chunks SET embedding = NULL WHERE embedding IS NOT NULL")
    op.alter_column(
        "chunks",
        "embedding",
        type_=pgvector.sqlalchemy.vector.VECTOR(dim=384),
        existing_nullable=True,
    )
    op.create_index(
        "chunks_embedding_idx",
        "chunks",
        ["embedding"],
        unique=False,
        postgresql_using="ivfflat",
        postgresql_with={"lists": 100},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
