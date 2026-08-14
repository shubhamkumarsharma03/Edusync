"""EduSync Seed Script

Populates the database with initial sample documents and circulars for local testing.
"""

import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_data() -> None:
    logger.info("EduSync seed script initialized. Ready to populate sample documents.")


if __name__ == "__main__":
    asyncio.run(seed_data())
