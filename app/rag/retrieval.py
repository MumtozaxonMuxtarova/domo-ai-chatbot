"""Local Chroma snapshots and cosine retrieval; no LLM or Telegram integration."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from app.rag.chunking import Chunk
from app.rag.embeddings import Embedder
from app.rag.errors import RetrievalError


@dataclass(frozen=True)
class RetrievalHit:
    chunk: Chunk
    score: float  # Cosine similarity, not a probability or confidence guarantee.


class Retriever:
    def __init__(self, chunks: list[Chunk], embedder: Embedder, path: Path, *, min_score: float = 0.80):
        if not chunks or len({chunk.id for chunk in chunks}) != len(chunks):
            raise ValueError("Chunks must be nonempty and have unique IDs")
        if not -1 <= min_score <= 1:
            raise ValueError("min_score must be between -1 and 1")
        self.chunks = tuple(chunks)
        self.by_id = {chunk.id: chunk for chunk in chunks}
        self.embedder = embedder
        self.min_score = min_score
        payload = json.dumps(
            {"schema": 1, "embedding": embedder.identity, "chunks": [asdict(chunk) for chunk in chunks]},
            ensure_ascii=False, sort_keys=True,
        )
        self.fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.collection_name = "domo_kb_" + self.fingerprint[:24]
        try:
            import chromadb
            from chromadb.config import Settings
            self.client = chromadb.PersistentClient(
                path=str(path.resolve()), settings=Settings(anonymized_telemetry=False)
            )
        except ImportError:
            raise RetrievalError("ChromaDB o'rnatilmagan. requirements-rag.txt ni o'rnating.") from None
        except Exception:
            raise RetrievalError("Lokal ChromaDB ochilmadi. Yo'l va yozish ruxsatini tekshiring.") from None

    def _vectors(self, vectors, expected_count: int):
        if len(vectors) != expected_count:
            raise RetrievalError("Embedding natijasining soni noto'g'ri.")
        for vector in vectors:
            if len(vector) != self.embedder.dimension or not all(math.isfinite(v) for v in vector):
                raise RetrievalError("Embedding o'lchami yoki qiymatlari noto'g'ri.")
            if not any(vector):
                raise RetrievalError("Nol embedding bilan cosine qidiruv bajarilmaydi.")
        return vectors

    def _open_index(self):
        from chromadb.errors import NotFoundError
        try:
            collection = self.client.get_collection(self.collection_name, embedding_function=None)
        except NotFoundError:
            raise RetrievalError("Joriy model va bilim bazasi uchun indeks yo'q. Avval index buyrug'ini bajaring.") from None
        metadata = collection.metadata or {}
        if metadata.get("fingerprint") != self.fingerprint or metadata.get("ready") is not True:
            raise RetrievalError("Indeks to'liq emas yoki modelga mos emas. index buyrug'ini qayta bajaring.")
        if collection.count() != len(self.chunks):
            raise RetrievalError("Indeksdagi bo'laklar soni noto'g'ri. Indeksni tekshiring.")
        return collection

    def index(self) -> dict:
        from chromadb.errors import NotFoundError
        try:
            try:
                existing = self.client.get_collection(self.collection_name, embedding_function=None)
            except NotFoundError:
                existing = None
            if existing is not None:
                if (existing.metadata or {}).get("ready") is True:
                    self._open_index()
                    return {"collection": self.collection_name, "chunks": len(self.chunks), "reused": True}
                # Only this incomplete derived snapshot is replaced, never KB files.
                self.client.delete_collection(self.collection_name)
            try:
                vectors = self._vectors(self.embedder.embed_documents([c.text for c in self.chunks]), len(self.chunks))
            except RetrievalError:
                raise
            except Exception:
                raise RetrievalError("Hujjat embeddinglari hisoblanmadi.") from None
            collection = self.client.create_collection(
                name=self.collection_name, embedding_function=None,
                configuration={"hnsw": {"space": "cosine"}},
                metadata={"fingerprint": self.fingerprint, "model": self.embedder.identity, "ready": False},
            )
            metadata = []
            for chunk in self.chunks:
                record = asdict(chunk)
                record.pop("id")
                record.pop("text")
                record["source_ids"] = json.dumps(chunk.source_ids)
                record["document_source_ids"] = json.dumps(chunk.document_source_ids)
                metadata.append(record)
            collection.add(
                ids=[chunk.id for chunk in self.chunks], documents=[chunk.text for chunk in self.chunks],
                embeddings=vectors, metadatas=metadata,
            )
            collection.modify(metadata={"fingerprint": self.fingerprint, "model": self.embedder.identity, "ready": True})
            return {"collection": self.collection_name, "chunks": collection.count(), "reused": False}
        except RetrievalError:
            raise
        except Exception:
            raise RetrievalError("Lokal Chroma indeksini yaratish bajarilmadi.") from None

    def search(self, question: str, *, language: str, top_k: int = 3, min_score: float | None = None) -> list[RetrievalHit]:
        if not isinstance(question, str) or not question.strip() or len(question) > 2000:
            raise ValueError("Question must contain 1–2000 characters")
        if language not in ("uz", "ru"):
            raise ValueError("language must be uz or ru")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or not 1 <= top_k <= 20:
            raise ValueError("top_k must be between 1 and 20")
        threshold = self.min_score if min_score is None else min_score
        if not -1 <= threshold <= 1:
            raise ValueError("min_score must be between -1 and 1")
        try:
            collection = self._open_index()
            available = sum(chunk.language == language for chunk in self.chunks)
            if not available:
                return []
            try:
                vector = self._vectors([self.embedder.embed_query(question.strip())], 1)[0]
            except (RetrievalError, ValueError):
                raise
            except Exception:
                raise RetrievalError("Savol embeddingi hisoblanmadi.") from None
            result = collection.query(
                query_embeddings=[vector], n_results=min(top_k, available),
                where={"language": language}, include=["distances"],
            )
            hits = []
            for chunk_id, distance in zip(result["ids"][0], result["distances"][0], strict=True):
                raw_score = 1.0 - float(distance)
                if not math.isfinite(raw_score):
                    raise RetrievalError("Qidiruv masofasi noto'g'ri.")
                score = max(-1.0, min(1.0, raw_score))
                if score >= threshold:
                    chunk = self.by_id[chunk_id]
                    if chunk.language != language:
                        raise RetrievalError("Qidiruv natijasining tili noto'g'ri.")
                    hits.append(RetrievalHit(chunk=chunk, score=score))
            return hits
        except (RetrievalError, ValueError):
            raise
        except Exception:
            raise RetrievalError("Lokal bilim bazasidan qidiruv bajarilmadi.") from None
