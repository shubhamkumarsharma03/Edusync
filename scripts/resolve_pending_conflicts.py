"""Admin script to inspect and resolve pending document conflicts in EduSync.

Usage:
  python scripts/resolve_pending_conflicts.py --dry-run
  python scripts/resolve_pending_conflicts.py --apply
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.abspath("backend"))

from db.session import async_session_maker
from models.conflict import Conflict
from models.document import Document
from sqlalchemy import select


async def main(apply: bool) -> None:
    async with async_session_maker() as session:
        stmt = select(Conflict).where(Conflict.resolved_at.is_(None))
        conflicts = (await session.execute(stmt)).scalars().all()

        print(f"Found {len(conflicts)} unresolved conflicts in the database.\n")

        for idx, c in enumerate(conflicts, start=1):
            doc_stmt = select(Document).where(Document.id.in_(c.document_ids))
            docs = (await session.execute(doc_stmt)).scalars().all()
            print(f"--- Conflict #{idx} [ID: {c.id}] ---")
            for d in docs:
                print(
                    f"  • Doc [{d.notice_sno}] status={d.status} date={d.notice_date}: {d.title}"
                )

            # Determine resolution based on document content
            snos = {d.notice_sno: d for d in docs}
            now = datetime.now(UTC)

            if "2026WEB0672" in snos and "2026WEB0673" in snos:
                note = "Admin verified: Non-conflicting circulars for distinct student cohorts (Sem III vs Sem VII)."
                print(f"  -> Recommended Resolution: Keep both documents fresh. {note}")
                if apply:
                    for d in docs:
                        d.status = "fresh"
                    c.resolved_by = "admin"
                    c.resolved_at = now
                    c.resolution_note = note

            elif "2026WEB0421" in snos and "2026WEB0460" in snos:
                note = "Admin verified: Revised schedule (2026WEB0460) supersedes earlier notice (2026WEB0421)."
                print(
                    f"  -> Recommended Resolution: Mark 2026WEB0421 as archived, 2026WEB0460 as fresh. {note}"
                )
                if apply:
                    snos["2026WEB0421"].status = "archived"
                    snos["2026WEB0460"].status = "fresh"
                    c.resolved_by = "admin"
                    c.resolved_at = now
                    c.resolution_note = note

            elif "2026WEB0005" in snos and "2026WEB0016" in snos:
                note = "Admin verified: Revised notice (2026WEB0016) supersedes earlier notice (2026WEB0005)."
                print(
                    f"  -> Recommended Resolution: Mark 2026WEB0005 as archived, 2026WEB0016 as fresh. {note}"
                )
                if apply:
                    snos["2026WEB0005"].status = "archived"
                    snos["2026WEB0016"].status = "fresh"
                    c.resolved_by = "admin"
                    c.resolved_at = now
                    c.resolution_note = note
            print()

        if apply:
            await session.commit()
            print("Successfully applied and committed all conflict resolutions!")
        else:
            print("Dry-run complete. Run with --apply to commit these resolutions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply", action="store_true", help="Apply resolutions to database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview resolutions without modifying DB",
    )
    args = parser.parse_args()

    if not args.apply and not args.dry_run:
        print("Please specify either --apply or --dry-run")
        sys.exit(1)

    asyncio.run(main(apply=args.apply))
