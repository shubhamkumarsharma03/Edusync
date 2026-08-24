"""EduSync Seed Script

Populates the database with initial sample documents and circulars for local testing.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import os
import sys

# Add backend directory to sys.path
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import config and models
from api.config import get_settings
from models import Chunk, Document
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def seed_data() -> None:
    logger.info("EduSync seed script initialized. Populating sample documents...")
    async with async_session_maker() as session:
        # Check if we already have documents
        result = await session.execute(text("SELECT COUNT(*) FROM documents"))
        count = result.scalar()
        if count and count > 0:
            logger.info(f"Database already has {count} documents. Skipping seed.")
            return

        # Create dummy documents
        doc1 = Document(
            source_url="https://ecajmer.ac.in/circulars/exam_schedule_2026.pdf",
            source_type="pdf",
            department="Examination",
            owner="Controller of Examinations",
            content_hash="hash_exam_schedule",
            status="fresh",
        )
        doc2 = Document(
            source_url="https://ecajmer.ac.in/notices/fee_submission_sem7.html",
            source_type="html",
            department="Accounts",
            owner="Accounts Section",
            content_hash="hash_fee_submission",
            status="fresh",
        )
        doc3 = Document(
            source_url="https://ecajmer.ac.in/departments/cs/syllabus_btech.pdf",
            source_type="pdf",
            department="CS/IT",
            owner="HOD CS",
            content_hash="hash_cs_syllabus",
            status="fresh",
        )

        session.add_all([doc1, doc2, doc3])
        await session.flush()  # to get IDs

        # Create dummy chunks (zero vectors for now)
        dummy_vector = [0.0] * 384

        chunks = [
            Chunk(
                document_id=doc1.id,
                content="B.Tech Semester 7 Mid-Term Examinations will commence from Sept 15, 2026. All students must bring their ID cards.",
                token_count=20,
                embedding=dummy_vector,
            ),
            Chunk(
                document_id=doc1.id,
                content="Exam schedule: CS-701 Cloud Computing on Monday 9 AM. CS-702 Machine Learning on Wednesday 9 AM.",
                token_count=18,
                embedding=dummy_vector,
            ),
            Chunk(
                document_id=doc2.id,
                content="The last date for depositing the odd semester tuition fee is August 30, 2026. A late fee of Rs 50/day will apply afterwards.",
                token_count=25,
                embedding=dummy_vector,
            ),
            Chunk(
                document_id=doc3.id,
                content="Syllabus for CS-702 Machine Learning includes Supervised Learning, Neural Networks, and Deep Learning applications.",
                token_count=15,
                embedding=dummy_vector,
            ),
        ]

        session.add_all(chunks)
        await session.commit()

        logger.info("Successfully populated database with 3 documents and 4 chunks.")


if __name__ == "__main__":
    asyncio.run(seed_data())
