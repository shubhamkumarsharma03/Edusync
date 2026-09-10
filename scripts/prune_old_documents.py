import sys
from pathlib import Path

# Add backend to sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

import asyncio
from db.session import async_session_maker
from models.document import Document
from models.chunk import Chunk
from models.conflict import Conflict
from sqlalchemy import select, delete, func

# The 4 notices ingested today to keep
KEEP_URLS = [
    "https://ecajmer.ac.in/uploads/circulars/1788594557231-it.pdf",
    "https://ecajmer.ac.in/uploads/circulars/1788594691753-cyber.pdf",
    "https://ecajmer.ac.in/uploads/circulars/1788594425530-ce_compressed (1).pdf",
    "https://ecajmer.ac.in/uploads/circulars/1789023048928-Document 249.pdf",
]

async def preview_and_prune(dry_run=True):
    async with async_session_maker() as session:
        # Find the 4 documents to keep
        keep_docs_stmt = select(Document).where(Document.source_url.in_(KEEP_URLS))
        keep_docs = (await session.execute(keep_docs_stmt)).scalars().all()
        keep_ids = [d.id for d in keep_docs]
        
        print(f"Found {len(keep_docs)} documents matching KEEP_URLS:")
        for d in keep_docs:
            chunk_count = await session.scalar(select(func.count(Chunk.id)).where(Chunk.document_id == d.id))
            print(f"  KEEP: [{d.id}] {d.source_url} ({chunk_count} chunks)")
            
        if len(keep_docs) < 4:
            print(f"WARNING: Expected 4 documents to keep, but only found {len(keep_docs)}!")
            
        # Count total documents and chunks
        total_docs = await session.scalar(select(func.count(Document.id)))
        total_chunks = await session.scalar(select(func.count(Chunk.id)))
        print(f"\nCurrent Database Totals: {total_docs} documents, {total_chunks} chunks.")
        
        # Documents to delete
        delete_docs_stmt = select(Document).where(Document.id.not_in(keep_ids))
        docs_to_delete = (await session.execute(delete_docs_stmt)).scalars().all()
        print(f"Documents to remove: {len(docs_to_delete)}")
        
        # Chunks to delete
        chunks_to_delete_count = await session.scalar(
            select(func.count(Chunk.id)).where(Chunk.document_id.not_in(keep_ids))
        )
        print(f"Chunks to remove: {chunks_to_delete_count}")
        
        if dry_run:
            print("\n[DRY RUN] No changes were committed.")
            return
            
        # Delete associated chunks
        await session.execute(delete(Chunk).where(Chunk.document_id.not_in(keep_ids)))
        # Delete documents
        await session.execute(delete(Document).where(Document.id.not_in(keep_ids)))
        # Clear conflicts if any
        await session.execute(delete(Conflict))

        # Reset other sources that now have 0 documents
        from models.source import IngestionSource
        sources = (await session.execute(select(IngestionSource))).scalars().all()
        for s in sources:
            if s.name != "CSE Circulars":
                s.status = "idle"
                s.last_fetched_at = None
                s.error_message = None
        
        await session.commit()
        
        # Verify
        remaining_docs = await session.scalar(select(func.count(Document.id)))
        remaining_chunks = await session.scalar(select(func.count(Chunk.id)))
        print(f"\n[SUCCESS] Pruning complete!")
        print(f"Remaining in DB: {remaining_docs} documents, {remaining_chunks} chunks.")

if __name__ == "__main__":
    dry_run = "--commit" not in sys.argv
    asyncio.run(preview_and_prune(dry_run=dry_run))
