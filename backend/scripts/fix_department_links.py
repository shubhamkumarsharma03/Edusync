"""Script to backfill and associate department_id for sources and documents."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from api.config import get_settings  # noqa: E402


async def fix() -> None:
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        print("1. Ensuring all needed departments exist in `departments` table...")
        # Check/create First Year
        r = await conn.execute(
            text("SELECT id FROM departments WHERE slug = 'first-year' OR name = 'First Year'")
        )
        fy_id = r.scalar()
        if not fy_id:
            r2 = await conn.execute(
                text(
                    "INSERT INTO departments (name, slug, code, category) VALUES ('First Year', 'first-year', 'FY', 'administration') RETURNING id"
                )
            )
            fy_id = r2.scalar()
            print(f"   Created First Year dept: id={fy_id}")
        else:
            print(f"   First Year dept already exists: id={fy_id}")

        # Check/create Economy / Humanities
        r = await conn.execute(
            text(
                "SELECT id FROM departments WHERE slug = 'economy' OR name = 'Humanities and Social Sciences'"
            )
        )
        econ_id = r.scalar()
        if not econ_id:
            r2 = await conn.execute(
                text(
                    "INSERT INTO departments (name, slug, code, category) VALUES ('Humanities and Social Sciences', 'economy', 'HSS', 'department') RETURNING id"
                )
            )
            econ_id = r2.scalar()
            print(f"   Created Humanities/Economy dept: id={econ_id}")
        else:
            print(f"   Humanities/Economy dept already exists: id={econ_id}")

        # Check/create Mandatory Disclosure / General Admin
        r = await conn.execute(
            text(
                "SELECT id FROM departments WHERE slug = 'mandatory-disclosure' OR name = 'General Admin'"
            )
        )
        gen_id = r.scalar()
        if not gen_id:
            r2 = await conn.execute(
                text(
                    "INSERT INTO departments (name, slug, code, category) VALUES ('General Admin', 'mandatory-disclosure', 'GEN', 'administration') RETURNING id"
                )
            )
            gen_id = r2.scalar()
            print(f"   Created General Admin dept: id={gen_id}")
        else:
            print(f"   General Admin dept already exists: id={gen_id}")

        print("\n2. Linking `ingestion_sources` to their corresponding `department_id`...")
        # Map by exact slug match
        await conn.execute(text("""
            UPDATE ingestion_sources s
            SET department_id = d.id
            FROM departments d
            WHERE s.slug = d.slug AND s.department_id IS NULL
        """))

        # Map special slugs:
        # 'maths' -> slug 'mathematics'
        await conn.execute(text("""
            UPDATE ingestion_sources s
            SET department_id = d.id
            FROM departments d
            WHERE s.slug = 'maths' AND d.slug = 'mathematics' AND s.department_id IS NULL
        """))

        # Map First Year
        await conn.execute(text(f"""
            UPDATE ingestion_sources
            SET department_id = {fy_id}
            WHERE slug = 'first-year' AND department_id IS NULL
        """))

        # Map Economy
        await conn.execute(text(f"""
            UPDATE ingestion_sources
            SET department_id = {econ_id}
            WHERE slug = 'economy' AND department_id IS NULL
        """))

        # Map Mandatory Disclosure
        await conn.execute(text(f"""
            UPDATE ingestion_sources
            SET department_id = {gen_id}
            WHERE slug = 'mandatory-disclosure' AND department_id IS NULL
        """))

        # Check how many sources are linked
        s_linked = await conn.execute(
            text("SELECT count(*) FROM ingestion_sources WHERE department_id IS NOT NULL")
        )
        s_total = await conn.execute(text("SELECT count(*) FROM ingestion_sources"))
        print(f"   Ingestion sources linked: {s_linked.scalar()} / {s_total.scalar()}")

        print("\n3. Linking existing `documents` to departments...")
        # Find CSE department id
        cse_r = await conn.execute(text("SELECT id FROM departments WHERE slug = 'cs-it'"))
        cse_id = cse_r.scalar()

        # Documents 1-6 from CSE have source_url containing 'uploads/circulars'
        if cse_id:
            await conn.execute(text(f"""
                UPDATE documents
                SET department_id = {cse_id}
                WHERE department_id IS NULL
                  AND (source_url LIKE '%uploads/circulars%' OR source_url LIKE '%cs%')
            """))

        # Documents 7-10 from First Year have source_url containing 'Orders/CAS' or 'Orders/UG' or 'Orders/CE'
        if fy_id:
            await conn.execute(text(f"""
                UPDATE documents
                SET department_id = {fy_id}
                WHERE department_id IS NULL
                  AND (source_url LIKE '%Orders/CAS%' OR source_url LIKE '%Orders/UG%' OR source_url LIKE '%Orders/CE%')
            """))

        d_linked = await conn.execute(
            text("SELECT count(*) FROM documents WHERE department_id IS NOT NULL")
        )
        d_total = await conn.execute(text("SELECT count(*) FROM documents"))
        print(f"   Documents linked: {d_linked.scalar()} / {d_total.scalar()}")

        print("\nCompleted fix_department_links successfully.")


if __name__ == "__main__":
    asyncio.run(fix())
