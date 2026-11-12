import pytest

from app.rag import __main__ as cli
from app.rag import settings
from app.rag.errors import RetrievalError
from scripts import retrieval_demo


def test_inspect_needs_no_model_or_network(monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("inspect must not load an embedding model")
    monkeypatch.setattr(cli, "SentenceTransformerEmbedder", forbidden)
    assert cli.main(["inspect"]) == 0
    assert '"files": 20' in capsys.readouterr().out


def test_demo_missing_model_has_safe_error_instead_of_traceback(monkeypatch, capsys):
    def fail(*args, **kwargs):
        raise RetrievalError("Embedding modeli lokal keshda topilmadi.")
    monkeypatch.setattr(retrieval_demo, "SentenceTransformerEmbedder", fail)
    assert retrieval_demo.main([]) == 2
    error = capsys.readouterr().err
    assert "lokal keshda" in error
    assert "Traceback" not in error


@pytest.mark.parametrize("revision", ["", "main"])
def test_custom_models_need_fixed_revision(monkeypatch, revision):
    monkeypatch.setattr(settings, "dotenv_values", lambda *args, **kwargs: {
        "EMBEDDING_MODEL": "local/custom-model", "EMBEDDING_REVISION": revision,
    })
    monkeypatch.setattr(settings.os, "environ", {})
    with pytest.raises(RetrievalError):
        settings.load_rag_settings()
