with open("backend/ingestion/embedder.py", "r", encoding="utf-8") as f:
    text = f.read()

# Add query cache to DocumentEmbedder
target = """class DocumentEmbedder:
    \"\"\"Hybrid document embedder supporting Jina Embeddings v3 API and local BAAI/bge-m3 fallback.\"\"\"

    _model: Any = None
    MODEL_NAME: str = "bge-m3"
    EMBEDDING_DIM: int = 1024"""

replacement = """class DocumentEmbedder:
    \"\"\"Hybrid document embedder supporting Jina Embeddings v3 API and local BAAI/bge-m3 fallback.\"\"\"

    _model: Any = None
    _query_cache: dict[str, list[float]] = {}
    _CACHE_MAX_SIZE: int = 1024
    MODEL_NAME: str = "bge-m3"
    EMBEDDING_DIM: int = 1024

    @classmethod
    def get_cached_query_embedding(cls, query: str) -> list[float] | None:
        return cls._query_cache.get(query.strip().lower())

    @classmethod
    def set_cached_query_embedding(cls, query: str, embedding: list[float]) -> None:
        key = query.strip().lower()
        if len(cls._query_cache) >= cls._CACHE_MAX_SIZE:
            # Pop first inserted item (FIFO eviction)
            cls._query_cache.pop(next(iter(cls._query_cache)))
        cls._query_cache[key] = embedding"""

assert target in text, "Target not found in embedder.py"
text = text.replace(target, replacement)

# Add caching logic to aembed_texts for single query
cache_hook_target = """        if self.jina_embedder:
            return await self.jina_embedder.aembed_texts(texts, task=task)"""

cache_hook_replacement = """        # Check cache if single query
        if len(texts) == 1 and task == "retrieval.query":
            cached = self.get_cached_query_embedding(texts[0])
            if cached is not None:
                return [cached]

        if self.jina_embedder:
            embeddings = await self.jina_embedder.aembed_texts(texts, task=task)
            if len(texts) == 1 and task == "retrieval.query" and embeddings:
                self.set_cached_query_embedding(texts[0], embeddings[0])
            return embeddings"""

assert cache_hook_target in text, "Cache hook target not found in embedder.py"
text = text.replace(cache_hook_target, cache_hook_replacement)

# Also cache local model encoding
local_hook_target = """        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        return [emb.tolist() for emb in embeddings]"""

local_hook_replacement = """        embeddings = model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        res = [emb.tolist() for emb in embeddings]
        if len(texts) == 1 and task == "retrieval.query" and res:
            self.set_cached_query_embedding(texts[0], res[0])
        return res"""

assert local_hook_target in text, "Local hook target not found in embedder.py"
text = text.replace(local_hook_target, local_hook_replacement)

with open("backend/ingestion/embedder.py", "w", encoding="utf-8") as f:
    f.write(text)

print("DocumentEmbedder updated with query embedding LRU cache!")

