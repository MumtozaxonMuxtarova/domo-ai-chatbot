"""Sentence Transformers adapter: local CPU inference, opt-in first download."""

from typing import Protocol

from app.rag.errors import RetrievalError
from app.rag.settings import RagSettings


class Embedder(Protocol):
    identity: str
    dimension: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerEmbedder:
    def __init__(self, settings: RagSettings, *, allow_download: bool = False):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise RetrievalError("Sentence Transformers o'rnatilmagan. requirements-rag.txt ni o'rnating.") from None
        try:
            self.model = SentenceTransformer(
                settings.model, revision=settings.revision, device="cpu",
                cache_folder=str(settings.cache_path), local_files_only=not allow_download,
                trust_remote_code=False, model_kwargs={"use_safetensors": True},
            )
            self.dimension = self.model.get_embedding_dimension()
            self.model.max_seq_length = min(512, self.model.max_seq_length)
            self.is_e5 = "e5" in settings.model.casefold()
            self.identity = f"{settings.model}@{settings.revision}|normalized|e5={self.is_e5}|dim={self.dimension}"
        except Exception:
            raise RetrievalError(
                "Embedding modeli yuklanmadi. Lokal keshni tekshiring; ilk yuklash uchun --download-model kerak."
            ) from None

    def token_count(self, text: str) -> int:
        prefix = "passage: " if self.is_e5 else ""
        return self._token_length(prefix + text)

    def _token_length(self, text: str) -> int:
        try:
            return len(self.model.tokenizer(text, truncation=False, add_special_tokens=True)["input_ids"])
        except Exception:
            raise RetrievalError("Matnni tokenlarga ajratish bajarilmadi.") from None

    def _encode(self, texts: list[str], *, query: bool) -> list[list[float]]:
        prefix = ("query: " if query else "passage: ") if self.is_e5 else ""
        for text in texts:
            count = self._token_length(prefix + text)
            if count > self.model.max_seq_length:
                raise ValueError("Embedding input exceeds model token limit; shorten query or chunks")
        try:
            return self.model.encode(
                [prefix + text for text in texts], normalize_embeddings=True, convert_to_numpy=True,
                show_progress_bar=False, batch_size=16,
            ).tolist()
        except Exception:
            raise RetrievalError("Embedding hisoblash bajarilmadi. Model va resurslarni tekshiring.") from None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts, query=False)

    def embed_query(self, text: str) -> list[float]:
        return self._encode([text], query=True)[0]
