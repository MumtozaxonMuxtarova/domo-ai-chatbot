"""Embedding adapter contracts with a fake module: no model load or network."""

import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.errors import RetrievalError
from app.rag.settings import RagSettings


@pytest.fixture
def fake_sentence_transformers(monkeypatch):
    loads = []
    models = []

    class FakeArray:
        def __init__(self, values):
            self.values = values

        def tolist(self):
            return self.values

    class FakeModel:
        def __init__(self, *args, **kwargs):
            loads.append((args, kwargs))
            models.append(self)
            self.max_seq_length = 1024
            self.tokenizer_calls = []
            self.encode_calls = []

        def get_embedding_dimension(self):
            return 3

        def tokenizer(self, text, **kwargs):
            self.tokenizer_calls.append((text, kwargs))
            special = 2 if kwargs.get("add_special_tokens") else 0
            return {"input_ids": list(range(len(text.split()) + special))}

        def encode(self, texts, **kwargs):
            self.encode_calls.append((texts, kwargs))
            return FakeArray([[1.0, 0.0, 0.0] for _ in texts])

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    return SimpleNamespace(module=module, loads=loads, models=models)


def test_default_model_load_is_local_cpu_and_disallows_remote_code_and_pickle(fake_sentence_transformers):
    settings = RagSettings()
    embedder = SentenceTransformerEmbedder(settings)
    args, kwargs = fake_sentence_transformers.loads[0]
    assert args == (settings.model,)
    assert kwargs["revision"] == settings.revision
    assert kwargs["cache_folder"] == str(settings.cache_path)
    assert kwargs["local_files_only"] is True
    assert kwargs["trust_remote_code"] is False
    assert kwargs["model_kwargs"]["use_safetensors"] is True
    assert kwargs["device"] == "cpu"
    assert embedder.dimension == 3
    assert embedder.model.max_seq_length == 512
    assert f"{settings.model}@{settings.revision}" in embedder.identity


def test_explicit_download_permission_flips_local_only_flag(fake_sentence_transformers):
    SentenceTransformerEmbedder(RagSettings(), allow_download=True)
    assert fake_sentence_transformers.loads[0][1]["local_files_only"] is False
    assert fake_sentence_transformers.loads[0][1]["trust_remote_code"] is False


def test_e5_documents_and_queries_have_distinct_prefixes_and_normalized_output(fake_sentence_transformers):
    embedder = SentenceTransformerEmbedder(RagSettings())
    documents = ["To‘lov hisobga tushmadi", "Платёж не поступил"]
    assert embedder.embed_documents(documents) == [[1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
    assert embedder.embed_query("Gaz hidi bor") == [1.0, 0.0, 0.0]
    assert embedder.model.encode_calls[0][0] == [f"passage: {text}" for text in documents]
    assert embedder.model.encode_calls[1][0] == ["query: Gaz hidi bor"]
    for _, kwargs in embedder.model.encode_calls:
        assert kwargs["normalize_embeddings"] is True
        assert kwargs["convert_to_numpy"] is True
        assert kwargs["show_progress_bar"] is False


def test_non_e5_model_does_not_receive_e5_prefixes(fake_sentence_transformers):
    settings = RagSettings(model="local/test-multilingual-model", revision="test-revision")
    embedder = SentenceTransformerEmbedder(settings)
    embedder.embed_documents(["Suv haqida"])
    embedder.embed_query("Вопрос о воде")
    assert embedder.model.encode_calls[0][0] == ["Suv haqida"]
    assert embedder.model.encode_calls[1][0] == ["Вопрос о воде"]


def test_token_counter_includes_passage_prefix_and_special_tokens_without_truncation(fake_sentence_transformers):
    embedder = SentenceTransformerEmbedder(RagSettings())
    text = "Suv ta’minoti"
    assert embedder.token_count(text) == 5  # Prefix + two words + two special tokens.
    assert embedder.model.tokenizer_calls[-1] == (
        "passage: " + text, {"truncation": False, "add_special_tokens": True}
    )


@pytest.mark.parametrize("operation", ["documents", "query"])
def test_over_token_limit_is_rejected_before_encode_instead_of_silently_truncated(fake_sentence_transformers, operation):
    embedder = SentenceTransformerEmbedder(RagSettings())
    embedder.model.max_seq_length = 4
    with pytest.raises(ValueError, match="token limit"):
        if operation == "documents":
            embedder.embed_documents(["one two three four"])
        else:
            embedder.embed_query("one two three four")
    assert embedder.model.encode_calls == []
    assert embedder.model.tokenizer_calls[-1][1]["truncation"] is False


def test_model_initialization_failure_has_safe_error_without_raw_details(fake_sentence_transformers, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("private-token-or-cache-error")

    monkeypatch.setattr(fake_sentence_transformers.module, "SentenceTransformer", fail)
    with pytest.raises(RetrievalError) as error:
        SentenceTransformerEmbedder(RagSettings())
    assert "private-token-or-cache-error" not in str(error.value)
    assert "--download-model" in str(error.value)


def test_encode_failure_hides_raw_exception_and_user_question(fake_sentence_transformers, monkeypatch):
    embedder = SentenceTransformerEmbedder(RagSettings())

    def fail(texts, **kwargs):
        raise RuntimeError("private-api-token-encode-error")

    monkeypatch.setattr(embedder.model, "encode", fail)
    with pytest.raises(RetrievalError) as error:
        embedder.embed_query("private-user-question")
    assert "private-api-token-encode-error" not in str(error.value)
    assert "private-user-question" not in str(error.value)


@pytest.mark.parametrize("operation", ["count", "documents", "query"])
def test_tokenizer_failure_never_exposes_input_or_internal_error(fake_sentence_transformers, monkeypatch, operation):
    embedder = SentenceTransformerEmbedder(RagSettings())
    def fail(*args, **kwargs):
        raise RuntimeError("private-tokenizer-error")
    monkeypatch.setattr(embedder.model, "tokenizer", fail)
    with pytest.raises(RetrievalError) as error:
        if operation == "count":
            embedder.token_count("private-input")
        elif operation == "documents":
            embedder.embed_documents(["private-input"])
        else:
            embedder.embed_query("private-input")
    assert "private" not in str(error.value)
