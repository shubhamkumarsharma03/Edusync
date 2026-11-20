"""add_notice_date_and_sno_to_documents

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-20 22:30:00.000000

"""

import re
from collections.abc import Sequence
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Session

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add columns to documents table
    op.add_column("documents", sa.Column("notice_sno", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("notice_date", sa.Date(), nullable=True))
    op.add_column("documents", sa.Column("portal_id", sa.Integer(), nullable=True))

    # 2. Create index for matching college portal chronological order
    op.create_index(
        "idx_documents_portal_order",
        "documents",
        [
            sa.text("notice_date DESC NULLS LAST"),
            sa.text("notice_sno DESC NULLS LAST"),
            sa.text("portal_id DESC NULLS LAST"),
        ],
    )

    # 3. Backfill existing records from first chunk content
    bind = op.get_bind()
    session = Session(bind=bind)

    doc_rows = session.execute(sa.text("SELECT id, source_url FROM documents")).fetchall()
    for doc_id, source_url in doc_rows:
        chunk_row = session.execute(
            sa.text("SELECT content FROM chunks WHERE document_id = :doc_id ORDER BY id ASC LIMIT 1"),
            {"doc_id": doc_id},
        ).fetchone()

        sno, parsed_date, portal_id = None, None, None
        if chunk_row and chunk_row[0]:
            content = chunk_row[0]
            # Match S.No
            m_sno = re.search(r"\*\*Notice S\.No:\*\*\s*([^\n\r]+)", content)
            if not m_sno:
                m_sno = re.search(r"Ref:\s*([^\s\|\]]+)", content)
            if m_sno:
                sno = m_sno.group(1).strip()

            # Match Date
            m_dt = re.search(r"\*\*Date:\*\*\s*([^\n\r]+)", content)
            if not m_dt:
                m_dt = re.search(r"Date:\s*([^\s\|\]]+)", content)
            if m_dt:
                raw_d = m_dt.group(1).strip()
                try:
                    raw_d = raw_d.replace("/", "-")
                    if "T" in raw_d:
                        raw_d = raw_d.split("T")[0]
                    parsed_date = date.fromisoformat(raw_d)
                except Exception:
                    pass

        # Try to infer S.No from URL if still None (e.g. 2025WEB0804)
        if not sno and source_url:
            m_url_sno = re.search(r"(20\d{2}WEB\d{4})", source_url)
            if m_url_sno:
                sno = m_url_sno.group(1)

        # Infer portal id if sno is in standard format (e.g. 2026WEB0889 -> 889)
        if sno and "WEB" in sno:
            digits = re.findall(r"\d+", sno.split("WEB")[-1])
            if digits:
                try:
                    portal_id = int(digits[0])
                except Exception:
                    pass

        if sno or parsed_date or portal_id:
            session.execute(
                sa.text(
                    "UPDATE documents SET notice_sno = :sno, notice_date = :ndt, portal_id = :pid WHERE id = :id"
                ),
                {"sno": sno, "ndt": parsed_date, "pid": portal_id, "id": doc_id},
            )

    session.commit()


def downgrade() -> None:
    op.drop_index("idx_documents_portal_order", table_name="documents")
    op.drop_column("documents", "portal_id")
    op.drop_column("documents", "notice_date")
    op.drop_column("documents", "notice_sno")
