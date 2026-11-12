"""Small validated content schemas; both languages are required."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

NonEmpty = Annotated[str, Field(min_length=1, max_length=3500, pattern=r"\S")]
Identifier = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]*$")]
Category = Literal["electricity", "gas", "water", "heating", "general"]


class ContentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Localized(ContentModel):
    uz: NonEmpty
    ru: NonEmpty

    def text(self, language: str) -> str:
        if language not in ("uz", "ru"):
            raise ValueError("Unsupported content language")
        return getattr(self, language)


class Source(ContentModel):
    id: Identifier
    title: Localized
    url: HttpUrl
    scope: Literal["uzbekistan", "general_safety"]


class Document(ContentModel):
    id: Identifier
    category: Category
    title: Localized
    files: Localized
    content_type: Literal["demo_guidance", "demo_with_official_safety"]
    source_ids: tuple[Identifier, ...]


class DocumentIndex(ContentModel):
    schema_version: Literal[1]
    sources: tuple[Source, ...]
    documents: Annotated[tuple[Document, ...], Field(min_length=1)]


class FaqItem(ContentModel):
    id: Identifier
    category: Category
    question: Localized
    answer: Localized
    source_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    requires_account_data: bool
    status: Literal["draft", "approved"]
    content_type: Literal["demo_guidance"]
    updated_at: date


class FaqData(ContentModel):
    schema_version: Literal[1]
    items: Annotated[tuple[FaqItem, ...], Field(min_length=1)]


class SupportAnswer(ContentModel):
    id: Identifier
    question: Localized
    answer: Localized
    document_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    source_ids: tuple[Identifier, ...]


class ContactNumber(ContentModel):
    number: Literal["101", "112", "104", "1154"]
    purpose: Localized
    source_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


class SupportData(ContentModel):
    schema_version: Literal[1]
    utilities: Annotated[tuple[SupportAnswer, ...], Field(min_length=1)]
    safety: Annotated[tuple[SupportAnswer, ...], Field(min_length=1)]
    limitations: Localized
    safety_menu_label: Localized
    home_label: Localized
    safety_intro: Localized
    numbers: tuple[ContactNumber, ...]
