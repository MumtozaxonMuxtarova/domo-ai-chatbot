import logging

from app.logging_config import SafeFormatter


def make_record(name, message, args=(), exc_info=None):
    return logging.LogRecord(name, logging.ERROR, __file__, 1, message, args, exc_info)


def test_tokens_are_hidden_without_mutating_record():
    token = "123456789:" + "a" * 35
    record = make_record("app.main", "token=%s custom=private-secret gsk_abcdef", (token,))
    result = SafeFormatter(["private-secret"]).format(record)
    assert token not in result
    assert "private-secret" not in result
    assert "gsk_abcdef" not in result
    assert record.args == (token,)


def test_third_party_text_and_exception_details_are_hidden():
    error = ValueError("private card=1234 password=private")
    record = make_record("aiogram.event", "raw user input", exc_info=(ValueError, error, None))
    result = SafeFormatter().format(record)
    assert "raw user input" not in result
    assert "private" not in result
    assert "ValueError" in result


def test_application_exception_preserves_type_only():
    error = RuntimeError("sensitive customer text")
    result = SafeFormatter().format(make_record(
        "app.main", "Startup failed", exc_info=(RuntimeError, error, None)
    ))
    assert "Startup failed" in result
    assert "RuntimeError" in result
    assert "sensitive" not in result
