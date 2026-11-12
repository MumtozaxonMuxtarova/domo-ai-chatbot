"""Standalone local retrieval CLI; never calls Groq or Telegram."""

import argparse
import json
import sys

from app.faq import KnowledgeBaseError, load_catalog
from app.rag.chunking import build_chunks
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.errors import RetrievalError
from app.rag.retrieval import Retriever
from app.rag.settings import load_rag_settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="DOMO — local retrieval only")
    parser.add_argument("action", choices=("inspect", "index", "query"))
    parser.add_argument("question", nargs="?")
    parser.add_argument("--language", choices=("uz", "ru"), default="uz")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--download-model", action="store_true", help="Allow first model download")
    args = parser.parse_args(argv)
    try:
        catalog = load_catalog()
        if args.action == "inspect":
            chunks = build_chunks(catalog)
            print(json.dumps({"files": len(catalog.document_texts), "chunks": len(chunks), "model_loaded": False}))
            return 0
        if args.action == "query" and not args.question:
            parser.error("query requires a question")
        settings = load_rag_settings()
        embedder = SentenceTransformerEmbedder(settings, allow_download=args.download_model)
        chunks = build_chunks(catalog, token_counter=embedder.token_count)
        retriever = Retriever(chunks, embedder, settings.chroma_path, min_score=settings.min_score)
        if args.action == "index":
            print(json.dumps(retriever.index(), ensure_ascii=False))
        else:
            hits = retriever.search(args.question, language=args.language, top_k=args.top_k, min_score=args.min_score)
            results = []
            for hit in hits:
                chunk = hit.chunk
                results.append({
                    "document_id": chunk.document_id, "language": chunk.language, "score": round(hit.score, 4),
                    "title": chunk.title, "section": chunk.section, "filename": chunk.filename,
                    "text": chunk.text, "content_type": chunk.content_type,
                    "source_ids": list(chunk.source_ids),
                    "sources": [{"id": key, "url": str(catalog.sources[key].url)} for key in chunk.source_ids],
                })
            print(json.dumps({"results": results, "answer_generated": False}, ensure_ascii=False, indent=2))
        return 0
    except (RetrievalError, KnowledgeBaseError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except ValueError:
        print("Qidiruv savoli yoki parametrlari noto'g'ri.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
