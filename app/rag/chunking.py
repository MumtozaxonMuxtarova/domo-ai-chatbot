"""Deterministic section-aware chunks from the 20 indexed bilingual documents."""

import hashlib
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from app.faq import KnowledgeCatalog


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    language: str
    category: str
    title: str
    section: str
    text: str
    filename: str
    content_type: str
    source_ids: tuple[str, ...]
    document_source_ids: tuple[str, ...]
    chunk_index: int


def _sections(markdown: str) -> Iterator[tuple[str, str]]:
    section = ""
    lines: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("## "):
            if lines and section not in ("Manbalar", "Источники"):
                body = "\n".join(lines).strip()
                if body:
                    yield section or "Overview", body
            section, lines = line[3:].strip(), []
            continue
        if line.startswith(("ID:", "Til:", "Язык:", "**DEMO")):
            continue
        lines.append(line)
    if lines and section not in ("Manbalar", "Источники"):
        body = "\n".join(lines).strip()
        if body:
            yield section or "Overview", body


def _windows(body, prefix, max_chars, overlap_chars, token_counter, max_tokens):
    room = max_chars - len(prefix)
    if room < 32 or overlap_chars >= room:
        raise ValueError("Chunk limit is too small for its title/section or overlap")
    start = 0
    while start < len(body):
        end = min(start + room, len(body))
        if end < len(body):
            boundary = body.rfind(" ", start + room // 2, end)
            if boundary > start:
                end = boundary
        while token_counter is not None and token_counter(prefix + body[start:end]) > max_tokens:
            end = start + (end - start) * 3 // 4
            if end <= start:
                raise ValueError("Token budget is too small for the chunk prefix")
        piece = body[start:end].strip()
        if piece:
            yield prefix + piece
        if end == len(body):
            break
        start = max(start + 1, end - overlap_chars)


def build_chunks(
    catalog: KnowledgeCatalog, *, max_chars: int = 900, overlap_chars: int = 100,
    token_counter: Callable[[str], int] | None = None, max_tokens: int = 480,
) -> list[Chunk]:
    if max_chars < 128 or overlap_chars < 0 or overlap_chars >= max_chars or max_tokens < 1:
        raise ValueError("Invalid chunk limits")
    chunks = []
    for document in catalog.documents.values():
        for language in ("uz", "ru"):
            title = document.title.text(language)
            ordinal = 0
            for section, body in _sections(catalog.document_texts[(document.id, language)]):
                is_safety = section.startswith(("Xavfsizlik javobi", "Ответ по безопасности"))
                is_ordinary = section in ("Oddiy muammo uchun javob", "Ответ при обычной проблеме")
                refs = set()
                if is_safety or is_ordinary:
                    answers = catalog.support.safety if is_safety else catalog.support.utilities
                    for answer in answers:
                        if document.id in answer.document_ids:
                            refs.update(answer.source_ids)
                prefix = f"{title}\n{section}\n\n"
                for text in _windows(body, prefix, max_chars, overlap_chars, token_counter, max_tokens):
                    identity = f"{document.id}|{language}|{section}|{ordinal}|{text}"
                    chunks.append(Chunk(
                        id=hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                        document_id=document.id, language=language, category=document.category,
                        title=title, section=section, text=text, filename=document.files.text(language),
                        content_type=document.content_type, source_ids=tuple(sorted(refs)),
                        document_source_ids=document.source_ids, chunk_index=ordinal,
                    ))
                    ordinal += 1
    return chunks
