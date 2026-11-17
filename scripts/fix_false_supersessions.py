import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from db.session import async_session_maker
from models.notice_memory import NoticeMemory
from sqlalchemy import select


async def main():
    async with async_session_maker() as session:
        stmt = select(NoticeMemory).where(NoticeMemory.is_latest == False)
        superseded_records = (await session.execute(stmt)).scalars().all()
        print(f"Total currently marked superseded: {len(superseded_records)}")

        reinstated = 0
        for old in superseded_records:
            if not old.superseded_by:
                continue

            sup_stmt = select(NoticeMemory).where(NoticeMemory.id == old.superseded_by)
            sup_res = (await session.execute(sup_stmt)).scalar_one_or_none()
            if not sup_res:
                old.is_latest = True
                old.superseded_by = None
                old.supersession_reason = None
                reinstated += 1
                continue

            old_words = set(re.findall(r"\b\w{4,}\b", old.title_summary.lower()))
            new_words = set(re.findall(r"\b\w{4,}\b", sup_res.title_summary.lower()))
            overlap = old_words.intersection(new_words)

            # Filter out common college stopwords from overlap
            overlap = {
                w
                for w in overlap
                if w not in ("notice", "college", "ajmer", "engineering", "regarding", "session")
            }

            if not overlap:
                print(
                    f"Reinstating falsely superseded notice: '{old.title_summary[:45]}' (was superseded by '{sup_res.title_summary[:45]}')"
                )
                old.is_latest = True
                old.superseded_by = None
                old.supersession_reason = None
                reinstated += 1
            else:
                print(
                    f"Keeping genuine supersession: '{old.title_summary[:45]}' -> '{sup_res.title_summary[:45]}' (overlap={overlap})"
                )

        await session.commit()
        print(f"\nSuccessfully reinstated {reinstated} falsely superseded notices to is_latest=True.")


if __name__ == "__main__":
    asyncio.run(main())

