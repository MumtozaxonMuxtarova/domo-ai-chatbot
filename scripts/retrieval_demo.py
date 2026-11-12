"""Repeatable local multilingual retrieval evaluation; not a production benchmark."""

import argparse
import json
import sys
from pathlib import Path

# Allow the beginner-friendly `python scripts/retrieval_demo.py` invocation.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.faq import KnowledgeBaseError, load_catalog
from app.rag.chunking import build_chunks
from app.rag.embeddings import SentenceTransformerEmbedder
from app.rag.retrieval import Retriever
from app.rag.settings import load_rag_settings
from app.rag.errors import RetrievalError

CASES = [
    ("uz", "Elektr hisobimdagi qoldiqni qayerdan tekshiraman?", "electricity_balance"),
    ("ru", "Как узнать остаток денег на счёте за электричество?", "electricity_balance"),
    ("uz", "Elektr, gaz va suv uchun to‘lovni qanday qilaman?", "utility_payments"),
    ("ru", "Как оплатить коммунальные услуги?", "utility_payments"),
    ("uz", "Pul kartamdan yechildi, ammo kommunal hisobga tushmadi. Nima qilay?", "payment_delay"),
    ("ru", "Деньги списались, но платёж не появился на коммунальном счёте.", "payment_delay"),
    ("uz", "Kommunal xizmatlar bo‘yicha qarzimni qanday tekshiraman?", "debt_check"),
    ("ru", "Как проверить задолженность за коммунальные услуги?", "debt_check"),
    ("uz", "Uyda gaz hidi kelyapti, nima qilishim kerak?", "gas_issues"),
    ("ru", "В квартире пахнет газом. Что делать?", "gas_issues"),
    ("uz", "Suv rozetkaga tegib ketdi, elektrni o‘chirish uchun suvga kirsam bo‘ladimi?", "water_issues"),
    ("ru", "Вода дошла до розеток, можно ли зайти в воду и выключить электричество?", "water_issues"),
    ("uz", "Radiatorlar sovuq, isitish ishlamayapti. Kimga murojaat qilaman?", "heating_issues"),
    ("ru", "Батареи холодные, отопление не работает. Куда обратиться?", "heating_issues"),
    ("uz", "Uyda yong‘in boshlandi. Kimga qo‘ng‘iroq qilaman?", "fire_safety"),
    ("ru", "В квартире пожар. По какому номеру звонить?", "fire_safety"),
    ("uz", "Mars sayyorasida hayot bormi?", None),
    ("ru", "Как приготовить шоколадный торт?", None),
    ("uz", "Bugungi futbol o‘yinida kim g‘alaba qozondi?", None),
    ("ru", "Какая погода будет завтра в Париже?", None),
]


def _run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    settings = load_rag_settings()
    embedder = SentenceTransformerEmbedder(settings)  # Cached model only.
    chunks = build_chunks(load_catalog(), token_counter=embedder.token_count)
    retriever = Retriever(chunks, embedder, settings.chroma_path, min_score=settings.min_score)
    rows = []
    for language, question, expected in CASES:
        raw = retriever.search(question, language=language, top_k=3, min_score=-1)
        accepted = [hit for hit in raw if hit.score >= settings.min_score]
        rows.append({
            "language": language, "question": question, "expected_document": expected,
            "passed": any(hit.chunk.document_id == expected for hit in accepted) if expected else not accepted,
            "top": [{"document_id": hit.chunk.document_id, "score": round(hit.score, 4),
                     "section": hit.chunk.section, "accepted": hit.score >= settings.min_score} for hit in raw],
        })
    result = {
        "model": embedder.identity, "collection": retriever.collection_name,
        "chunk_count": len(chunks), "min_score": settings.min_score,
        "passed": sum(row["passed"] for row in rows), "total": len(rows),
        "note": "Small local smoke set; scores are cosine similarity, not probabilities. No answers generated.",
        "cases": rows,
    }
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    print(output)
    return 0 if all(row["passed"] for row in rows) else 1


def main(argv=None):
    try:
        return _run(argv)
    except (RetrievalError, KnowledgeBaseError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError):
        print("Demo parametri yoki natija fayli bilan ishlashda xatolik.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
