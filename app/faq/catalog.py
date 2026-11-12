"""Read and validate local content once at startup. Never store user messages."""

import unicodedata
from pathlib import Path

from pydantic import BaseModel, ValidationError

from app.config import PROJECT_ROOT
from app.faq.models import DocumentIndex, FaqData, SupportData

DEFAULT_KB_ROOT = PROJECT_ROOT / "knowledge_base"


class KnowledgeBaseError(ValueError):
    """Safe content error; no raw file contents or user data in the message."""


def normalize_label(text: str) -> str:
    """Match selected questions, not free-text intent or safety classification."""
    value = unicodedata.normalize("NFKC", text)
    value = value.translate(str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'"}))
    # Permit typing an exact menu question without its decorative emoji.
    value = value.lstrip()
    while value and not value[0].isalnum() and value[0] != "/":
        value = value[1:]
    return " ".join(value.casefold().split())


def _read_json(root: Path, name: str, schema: type[BaseModel]):
    try:
        return schema.model_validate_json((root / name).read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, ValidationError):
        raise KnowledgeBaseError(
            f"Bilim bazasi fayli yo'q yoki noto'g'ri: {name}. Fayl va ikkala tilni tekshiring."
        ) from None


def _unique(items, name: str):
    result = {}
    for item in items:
        if item.id in result:
            raise KnowledgeBaseError(f"Bilim bazasida takroriy ID mavjud: {name}.")
        result[item.id] = item
    return result


class KnowledgeCatalog:
    def __init__(self, root: Path, index: DocumentIndex, faq: FaqData, support: SupportData):
        self.root = root
        self.index = index
        self.faq = faq
        self.support = support
        self.sources = _unique(index.sources, "sources")
        self.documents = _unique(index.documents, "documents")
        self.faq_items = _unique(faq.items, "faq")
        self.utilities = _unique(support.utilities, "utilities")
        self.safety = _unique(support.safety, "safety")
        self.document_texts: dict[tuple[str, str], str] = {}
        self._labels = {}
        self._validate_references()
        self._load_documents()
        self._index_labels()

    def _check_refs(self, ids, target) -> None:
        if any(value not in target for value in ids):
            raise KnowledgeBaseError("Bilim bazasida mavjud bo'lmagan manba yoki hujjatga havola bor.")

    def _validate_references(self) -> None:
        for source in self.sources.values():
            if source.url.scheme != "https":
                raise KnowledgeBaseError("Rasmiy manba havolasi HTTPS bo'lishi kerak.")
        for doc in self.documents.values():
            self._check_refs(doc.source_ids, self.sources)
            if doc.content_type == "demo_with_official_safety" and not doc.source_ids:
                raise KnowledgeBaseError("Xavfsizlik hujjati uchun manba ko'rsatilmagan.")
        for item in self.faq.items:
            self._check_refs(item.source_ids, self.documents)
        for item in (*self.support.utilities, *self.support.safety):
            self._check_refs(item.document_ids, self.documents)
            self._check_refs(item.source_ids, self.sources)
        for item in self.support.safety:
            if not item.source_ids:
                raise KnowledgeBaseError("Xavfsizlik javobi uchun manba ko'rsatilmagan.")
        numbers = set()
        for number in self.support.numbers:
            if number.number in numbers:
                raise KnowledgeBaseError("Bilim bazasida takroriy aloqa raqami mavjud.")
            numbers.add(number.number)
            self._check_refs(number.source_ids, self.sources)

    def _load_documents(self) -> None:
        used_paths = set()
        for doc in self.documents.values():
            for language in ("uz", "ru"):
                filename = doc.files.text(language)
                candidate = (self.root / filename).resolve()
                if not candidate.is_relative_to(self.root) or candidate.suffix != ".md":
                    raise KnowledgeBaseError("Bilim hujjati yo'li knowledge_base ichidagi Markdown fayli bo'lishi kerak.")
                if candidate in used_paths:
                    raise KnowledgeBaseError("Bilim hujjatlari bir xil faylga ishora qilmoqda.")
                used_paths.add(candidate)
                try:
                    body = candidate.read_text(encoding="utf-8-sig").strip()
                except (OSError, UnicodeError):
                    raise KnowledgeBaseError("Bilim hujjatini o'qib bo'lmadi. index.json dagi fayllarni tekshiring.") from None
                if not body.startswith("# ") or "DEMO" not in body:
                    raise KnowledgeBaseError("Bilim hujjati sarlavha va DEMO belgisiga ega bo'lishi kerak.")
                self.document_texts[(doc.id, language)] = body

    def _index_labels(self) -> None:
        for group, items in (
            ("faq", tuple(item for item in self.faq.items if item.status == "approved")),
            ("utility", self.support.utilities), ("safety", self.support.safety),
        ):
            for item in items:
                for language in ("uz", "ru"):
                    key = normalize_label(item.question.text(language))
                    if key in self._labels and self._labels[key] != (group, item.id):
                        raise KnowledgeBaseError("Bilim bazasidagi savollar bir-birini takrorlaydi.")
                    self._labels[key] = (group, item.id)

    def find_question(self, text: str) -> tuple[str, str] | None:
        return self._labels.get(normalize_label(text))

    def format_support(self, group: str, item_id: str, language: str) -> str:
        groups = {"utility": self.utilities, "safety": self.safety}
        item = groups[group][item_id]
        answer = item.answer.text(language)
        if item.source_ids:
            heading = "Manbalar:" if language == "uz" else "Источники:"
            links = [f"{self.sources[key].title.text(language)}\n{self.sources[key].url}" for key in item.source_ids]
            answer += "\n\n" + heading + "\n" + "\n\n".join(links)
        if len(answer.encode("utf-16-le")) // 2 > 4096:
            raise KnowledgeBaseError("FAQ javobi Telegram xabari chegarasidan uzun.")
        return answer


def load_catalog(root: Path | None = None) -> KnowledgeCatalog:
    resolved = (DEFAULT_KB_ROOT if root is None else root).resolve()
    catalog = KnowledgeCatalog(
        resolved,
        _read_json(resolved, "index.json", DocumentIndex),
        _read_json(resolved, "faq.json", FaqData),
        _read_json(resolved, "support.json", SupportData),
    )
    # Validate outbound lengths before polling starts, not during an emergency.
    for language in ("uz", "ru"):
        for item in catalog.faq.items:
            if len(item.answer.text(language).encode("utf-16-le")) // 2 > 4096:
                raise KnowledgeBaseError("FAQ javobi Telegram xabari chegarasidan uzun.")
        for group, items in (("utility", catalog.utilities), ("safety", catalog.safety)):
            for item_id in items:
                catalog.format_support(group, item_id, language)
    return catalog
