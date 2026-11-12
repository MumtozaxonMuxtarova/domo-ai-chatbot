"""Offline knowledge validation: python -m app.faq. No .env or API access."""

import sys

from app.faq import KnowledgeBaseError, load_catalog


def main() -> int:
    try:
        catalog = load_catalog()
    except KnowledgeBaseError as error:
        print(f"Bilim bazasi xatosi: {error}", file=sys.stderr)
        return 2
    approved = sum(item.status == "approved" for item in catalog.faq.items)
    print(
        f"Bilim bazasi tekshirildi: {approved} FAQ, "
        f"{len(catalog.documents)} hujjat / {len(catalog.document_texts)} til fayli, "
        f"{len(catalog.safety)} xavfsizlik javobi. API ishlatilmadi."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
