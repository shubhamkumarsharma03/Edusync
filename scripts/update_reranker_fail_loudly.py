with open("backend/retrieval/reranker.py", "r", encoding="utf-8") as f:
    text = f.read()

# Update arerank and rerank in CrossEncoderReranker
target = """    async def arerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        \"\"\"Asynchronously rerank candidate chunks.

        Uses Jina Reranker v2 API when available, otherwise runs local CPU model in threadpool.
        \"\"\"
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.jina_reranker:
            try:
                return await self.jina_reranker.arerank(query=query, chunks=chunks, top_n=top_k)
            except Exception as e:
                logger.warning(f"Jina reranker call failed ({e}). Falling back to local CrossEncoder.")

        import asyncio

        return await asyncio.to_thread(self.rerank, query=query, chunks=chunks, top_k=top_k)

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        \"\"\"Rerank candidate chunks using Cross-Encoder semantic matching.

        Returns top_k chunks sorted by descending reranker score.
        \"\"\"
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.jina_reranker:
            try:
                return self.jina_reranker.rerank(query=query, chunks=chunks, top_n=top_k)
            except Exception as e:
                logger.warning(f"Jina reranker call failed ({e}). Falling back to local CrossEncoder.")"""

replacement = """    async def arerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        \"\"\"Asynchronously rerank candidate chunks.

        Strictly enforces the configured provider without silent masking:
        - provider='jina': calls Jina AI API and fails loudly if an error occurs.
        - provider='local': runs local CPU CrossEncoder in threadpool.
        \"\"\"
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.provider == "jina":
            if not self.jina_reranker:
                raise RuntimeError("Reranker provider 'jina' was explicitly configured but is not available or unauthenticated.")
            return await self.jina_reranker.arerank(query=query, chunks=chunks, top_n=top_k)

        if self.provider == "auto" and self.jina_reranker:
            try:
                return await self.jina_reranker.arerank(query=query, chunks=chunks, top_n=top_k)
            except Exception as e:
                logger.error(f"Jina reranker call failed in auto mode: {e}")
                raise RuntimeError(f"Reranker failed loudly: {e}") from e

        import asyncio

        return await asyncio.to_thread(self.rerank, query=query, chunks=chunks, top_k=top_k)

    def rerank(
        self,
        query: str,
        chunks: Sequence[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        \"\"\"Rerank candidate chunks using Cross-Encoder semantic matching on local CPU.

        Returns top_k chunks sorted by descending reranker score.
        \"\"\"
        if not chunks or not query.strip():
            return list(chunks[:top_k])

        if self.provider == "jina":
            if not self.jina_reranker:
                raise RuntimeError("Reranker provider 'jina' was explicitly configured but is not available.")
            return self.jina_reranker.rerank(query=query, chunks=chunks, top_n=top_k)"""

assert target in text, "Target block not found in reranker.py"
text = text.replace(target, replacement)

# Support multi-model registry in CrossEncoderReranker
model_target = """    @classmethod
    def get_model(cls, model_name: str = DEFAULT_MODEL_NAME) -> Any:
        \"\"\"Lazy load CrossEncoder model as a singleton on CPU from local cache or Hub.\"\"\"
        if cls._model is None:
            from pathlib import Path

            from sentence_transformers import CrossEncoder

            # Check local models_cache folder
            base_model_name = model_name.split("/")[-1]
            local_cache_path = (
                Path(__file__).resolve().parent.parent / "models_cache" / base_model_name
            )
            target = str(local_cache_path) if local_cache_path.exists() else model_name

            logger.info(f"Loading CrossEncoder reranker model '{target}' on CPU...")
            cls._model = CrossEncoder(target, device="cpu")
        return cls._model"""

model_replacement = """    _loaded_models: dict[str, Any] = {}

    @classmethod
    def get_model(cls, model_name: str = DEFAULT_MODEL_NAME) -> Any:
        \"\"\"Lazy load CrossEncoder model keyed by model_name on CPU from local cache or Hub.\"\"\"
        if model_name not in cls._loaded_models:
            from pathlib import Path

            from sentence_transformers import CrossEncoder

            # Check local models_cache folder
            base_model_name = model_name.split("/")[-1]
            local_cache_path = (
                Path(__file__).resolve().parent.parent / "models_cache" / base_model_name
            )
            target = str(local_cache_path) if local_cache_path.exists() else model_name

            logger.info(f"Loading CrossEncoder reranker model '{target}' on CPU...")
            cls._loaded_models[model_name] = CrossEncoder(target, device="cpu")
        return cls._loaded_models[model_name]"""

assert model_target in text, "Model target not found in reranker.py"
text = text.replace(model_target, model_replacement)

with open("backend/retrieval/reranker.py", "w", encoding="utf-8") as f:
    f.write(text)

print("CrossEncoderReranker updated: fails loudly on error, no silent fallbacks, multi-model cache enabled!")

