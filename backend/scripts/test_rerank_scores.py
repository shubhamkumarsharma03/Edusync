import asyncio
from retrieval.reranker import CrossEncoderReranker
from db.session import async_session_maker
from models.chunk import Chunk
from models.document import Document
from sqlalchemy import select

async def test():
    async with async_session_maker() as session:
        reranker = CrossEncoderReranker()
        doc = (await session.execute(select(Document).where(Document.source_url.contains("249.pdf")))).scalar_one_or_none()
        chunks = (await session.execute(select(Chunk).where(Chunk.document_id == doc.id))).scalars().all()
        content = chunks[0].content
        for q in [
            "mtech timetable",
            "M.Tech time table timetable schedule",
            "M.Tech Computer Engineering time table schedule",
            "M.Tech 1st Sem Computer Engineering time table"
        ]:
            score = reranker.sigmoid(reranker.get_model().predict([(q, content)])[0])
            print(f"Query '{q}' -> Score: {score:.4f}")

if __name__ == "__main__":
    asyncio.run(test())
