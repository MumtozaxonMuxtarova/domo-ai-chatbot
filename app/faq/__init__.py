"""Approved static FAQ and local Markdown knowledge base. No AI calls."""

from app.faq.catalog import KnowledgeBaseError, KnowledgeCatalog, load_catalog

__all__ = ["KnowledgeBaseError", "KnowledgeCatalog", "load_catalog"]
