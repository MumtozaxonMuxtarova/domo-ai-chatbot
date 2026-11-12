"""Real local Chroma persistence with fake deterministic, network-free embeddings.

These tests validate vector retrieval plumbing, not multilingual model quality.
"""

from dataclasses import replace

import pytest

pytest.importorskip("chromadb")

from app.rag.chunking import Chunk
from app.rag.errors import RetrievalError
from app.rag.retrieval import Retriever


class FakeEmbedder:
    identity = "tests-three-axis-v1"
    dimension = 3

    def __init__(self):
        self.document_batches = 0

    @staticmethod
    def vector(text):
        text = text.casefold()
        if "partly" in text:
            return [0.6, 0.0, 0.8]
        if any(word in text for word in ("gas", "gaz", "газ")):
            return [1.0, 0.0, 0.0]
        if any(word in text for word in ("water", "suv", "вод")):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def embed_documents(self, texts):
        self.document_batches += 1
        return [self.vector(text) for text in texts]

    def embed_query(self, text):
        return self.vector(text)


def make_chunk(topic, language, text):
    return Chunk(
        id=f"test-{topic}-{language}", document_id=f"{topic}_guide", language=language,
        category="gas" if topic == "gas" else "water", title=f"{topic} guide",
        section="Instruction", text=text, filename=f"{topic}/guide.{language}.md",
        content_type="demo_guidance", source_ids=(), document_source_ids=(), chunk_index=0,
    )


@pytest.fixture
def chunks():
    return [
        make_chunk("gas", "uz", "Gaz sizishi haqida DEMO yo‘riqnoma [gas]"),
        make_chunk("gas", "ru", "DEMO инструкция при запахе газа [gas]"),
        make_chunk("water", "uz", "Suv ta’minoti uchun DEMO yo‘riqnoma [water]"),
        make_chunk("water", "ru", "DEMO инструкция по водоснабжению [water]"),
    ]


@pytest.fixture
def retriever(tmp_path, chunks):
    return Retriever(chunks, FakeEmbedder(), tmp_path / "chroma", min_score=0.8)


@pytest.mark.parametrize("language,question", [("uz", "Gaz hidi bor"), ("ru", "Запах газа")])
def test_local_retrieval_returns_relevant_canonical_chunk_in_requested_language(retriever, chunks, language, question):
    retriever.index()
    hits = retriever.search(question, language=language)
    assert len(hits) == 1
    assert hits[0].chunk == next(chunk for chunk in chunks if chunk.id == f"test-gas-{language}")
    assert hits[0].score == pytest.approx(1.0, abs=1e-6)
    assert all(hit.chunk.language == language for hit in hits)


def test_score_threshold_override_and_unrelated_query_fallback(retriever):
    retriever.index()
    assert retriever.search("unrelated question", language="uz") == []
    assert retriever.search("partly gas", language="uz") == []
    hits = retriever.search("partly gas", language="uz", min_score=0.5)
    assert len(hits) == 1
    assert hits[0].chunk.document_id == "gas_guide"
    assert hits[0].score == pytest.approx(0.6, abs=1e-6)
    assert retriever.search("partly gas", language="uz") == []


def test_top_k_limit_and_inclusive_exact_match_threshold(retriever):
    retriever.index()
    assert len(retriever.search("gas", language="uz", top_k=1, min_score=0.0)) == 1
    hits = retriever.search("gas", language="uz", min_score=1.0)
    assert len(hits) == 1
    assert hits[0].chunk.id == "test-gas-uz"


def test_index_is_persistent_and_repeat_index_reuses_snapshot(tmp_path, chunks):
    path = tmp_path / "chroma"
    first_embedder = FakeEmbedder()
    first = Retriever(chunks, first_embedder, path)
    built = first.index()
    assert built["chunks"] == len(chunks)
    assert built["reused"] is False
    assert first_embedder.document_batches > 0
    second_embedder = FakeEmbedder()
    reopened = Retriever(chunks, second_embedder, path)
    assert reopened.search("газ", language="ru")[0].chunk.id == "test-gas-ru"
    repeated = reopened.index()
    assert repeated["reused"] is True
    assert repeated["collection"] == built["collection"]
    assert repeated["chunks"] == len(chunks)
    assert second_embedder.document_batches == 0


def test_missing_index_never_silently_builds_or_downloads_model(tmp_path, chunks):
    embedder = FakeEmbedder()
    retriever = Retriever(chunks, embedder, tmp_path / "chroma")
    with pytest.raises(RetrievalError):
        retriever.search("gas", language="uz")
    assert embedder.document_batches == 0


def test_model_identity_change_requires_explicit_separate_index(tmp_path, chunks):
    path = tmp_path / "chroma"
    first = Retriever(chunks, FakeEmbedder(), path)
    initial = first.index()
    changed_embedder = FakeEmbedder()
    changed_embedder.identity = "tests-three-axis-v2"
    changed = Retriever(chunks, changed_embedder, path)
    with pytest.raises(RetrievalError):
        changed.search("gas", language="uz")
    rebuilt = changed.index()
    assert rebuilt["collection"] != initial["collection"]
    assert first.search("gas", language="uz")[0].chunk.id == "test-gas-uz"


def test_changed_chunk_snapshot_cannot_use_stale_collection(tmp_path, chunks):
    path = tmp_path / "chroma"
    first = Retriever(chunks, FakeEmbedder(), path)
    initial = first.index()
    changed_chunks = [replace(chunks[0], id="test-gas-uz-updated", text="Updated gas DEMO"), *chunks[1:]]
    changed = Retriever(changed_chunks, FakeEmbedder(), path)
    with pytest.raises(RetrievalError):
        changed.search("gas", language="uz")
    rebuilt = changed.index()
    assert rebuilt["collection"] != initial["collection"]
    assert changed.search("gas", language="uz")[0].chunk.id == "test-gas-uz-updated"


@pytest.mark.parametrize("kwargs", [
    {"question": "", "language": "uz"},
    {"question": "x" * 100_000, "language": "uz"},
    {"question": "gas", "language": "en"},
    {"question": "gas", "language": "uz", "top_k": 0},
    {"question": "gas", "language": "uz", "top_k": 21},
    {"question": "gas", "language": "uz", "min_score": 1.1},
])
def test_invalid_search_arguments_are_rejected(retriever, kwargs):
    with pytest.raises(ValueError):
        retriever.search(**kwargs)


def test_embedding_failure_is_reported_without_raw_details(tmp_path, chunks):
    class BrokenEmbedder(FakeEmbedder):
        def embed_documents(self, texts):
            raise RuntimeError("private-credential-error-detail")

    with pytest.raises(RetrievalError) as error:
        Retriever(chunks, BrokenEmbedder(), tmp_path / "chroma").index()
    assert "private-credential-error-detail" not in str(error.value)


def test_query_embedding_failure_is_reported_without_raw_question_or_error(tmp_path, chunks):
    path = tmp_path / "chroma"
    Retriever(chunks, FakeEmbedder(), path).index()

    class BrokenQueryEmbedder(FakeEmbedder):
        def embed_query(self, text):
            raise RuntimeError("private-query-error-detail")

    with pytest.raises(RetrievalError) as error:
        Retriever(chunks, BrokenQueryEmbedder(), path).search("private-user-question", language="uz")
    assert "private-query-error-detail" not in str(error.value)
    assert "private-user-question" not in str(error.value)
