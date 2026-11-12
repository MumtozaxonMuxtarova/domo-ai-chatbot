"""Local KB chunking contracts; these tests never load an embedding model."""

import pytest

from app.faq import load_catalog
from app.rag.chunking import build_chunks


@pytest.fixture
def catalog():
    return load_catalog()


def test_chunks_are_deterministic_and_cover_all_twenty_language_files(catalog):
    first = build_chunks(catalog)
    second = build_chunks(catalog)
    assert first
    assert [chunk.id for chunk in first] == [chunk.id for chunk in second]
    assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
    assert len({chunk.id for chunk in first}) == len(first)
    assert {(chunk.document_id, chunk.language) for chunk in first} == set(catalog.document_texts)
    assert len({chunk.filename for chunk in first}) == 20


def test_chunks_preserve_metadata_and_do_not_embed_repetitive_file_metadata(catalog):
    chunks = build_chunks(catalog)
    for chunk in chunks:
        document = catalog.documents[chunk.document_id]
        assert chunk.language in ("uz", "ru")
        assert chunk.category == document.category
        assert chunk.title == document.title.text(chunk.language)
        assert chunk.filename == document.files.text(chunk.language)
        assert chunk.content_type == document.content_type
        assert set(chunk.document_source_ids) == set(document.source_ids)
        assert set(chunk.source_ids) <= set(chunk.document_source_ids)
        assert chunk.chunk_index >= 0
        assert chunk.section.strip()
        assert chunk.text.strip()
        assert len(chunk.text) <= 900
        assert "\nID:" not in chunk.text
        assert "\nTil:" not in chunk.text
        assert "\nЯзык:" not in chunk.text
        assert "foydalanuvchi tasdiqlagan umumiy yo‘riqnoma" not in chunk.text
        assert "утверждённая пользователем общая инструкция" not in chunk.text
        assert chunk.section not in {"Manbalar", "Источники"}


def test_normal_and_safety_sections_do_not_mix_or_inherit_all_official_sources(catalog):
    chunks = build_chunks(catalog)
    gas_normal = [chunk for chunk in chunks if chunk.document_id == "gas_issues"
                  and chunk.language == "uz" and chunk.section == "Oddiy muammo uchun javob"]
    gas_safety = [chunk for chunk in chunks if chunk.document_id == "gas_issues"
                  and chunk.language == "uz" and chunk.section.startswith("Xavfsizlik javobi")]
    electricity_normal = [chunk for chunk in chunks if chunk.document_id == "electricity_issues"
                          and chunk.language == "uz" and chunk.section == "Oddiy muammo uchun javob"]
    assert gas_normal and gas_safety and electricity_normal
    assert all(not chunk.source_ids for chunk in gas_normal)
    assert all("Gaz sizishi ehtimoli bor." not in chunk.text for chunk in gas_normal)
    assert all("Gaz kelmayaptimi yoki bosim pasayganmi?" not in chunk.text for chunk in gas_safety)
    assert all("gas_advice" in chunk.source_ids for chunk in gas_safety)
    assert all(set(chunk.source_ids) == {"het_contact"} for chunk in electricity_normal)


def test_small_chunks_split_long_paragraphs_and_obey_full_text_token_budget(catalog):
    document = catalog.documents["debt_check"]
    catalog.document_texts[("debt_check", "uz")] = (
        f"# {document.title.uz}\n\n"
        "**DEMO**\n\nID: debt_check\n\nTil: o‘zbekcha\n\n"
        "## Batafsil yo‘riqnoma\n\n"
        + "Qarzdorlik masalasini rasmiy yordam xizmatida aniqlashtiring. " * 100
    )
    count_tokens = lambda text: len(text.split())
    chunks = build_chunks(
        catalog, max_chars=360, overlap_chars=40, token_counter=count_tokens, max_tokens=70
    )
    debt_uz = [chunk for chunk in chunks if chunk.document_id == "debt_check" and chunk.language == "uz"]
    assert len(debt_uz) > 1
    assert all(0 < len(chunk.text) <= 360 for chunk in chunks)
    assert all(count_tokens(chunk.text) <= 70 for chunk in chunks)
    assert len({chunk.id for chunk in debt_uz}) == len(debt_uz)


def test_changed_content_changes_corresponding_chunk_identity(catalog):
    before = {chunk.id for chunk in build_chunks(catalog)
              if chunk.document_id == "debt_check" and chunk.language == "uz"}
    catalog.document_texts[("debt_check", "uz")] += "\n\n## Qo‘shimcha\n\nFaqat DEMO ma’lumot.\n"
    after = {chunk.id for chunk in build_chunks(catalog)
             if chunk.document_id == "debt_check" and chunk.language == "uz"}
    assert after != before


@pytest.mark.parametrize("max_chars,overlap_chars", [(0, 0), (300, -1), (300, 300)])
def test_invalid_chunk_size_configuration_is_rejected(catalog, max_chars, overlap_chars):
    with pytest.raises(ValueError):
        build_chunks(catalog, max_chars=max_chars, overlap_chars=overlap_chars)
