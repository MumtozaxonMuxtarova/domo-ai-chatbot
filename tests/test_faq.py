"""Content contract tests against the user's approved text, not an LLM."""

import json
import shutil

import pytest

from app.faq import KnowledgeBaseError, load_catalog
from app.faq.catalog import DEFAULT_KB_ROOT

# Independent copies of the eight approved answers: wording and punctuation are fixed.
APPROVED_1_4 = [
    ("electricity_balance", "uz", "Men elektr hisobingizdagi qoldiqni ko‘ra olmayman. Balansni xizmat ko‘rsatuvchingiz taqdim etgan rasmiy usul orqali tekshiring. Qaysi tashkilot xizmat ko‘rsatishini aytsangiz, bizda shu tashkilot uchun tasdiqlangan yo‘riqnoma bor-yo‘qligini aniqlashtiraman. Hisobingiz holatini xizmat ko‘rsatuvchining rasmiy yordam xizmati tekshirishi kerak."),
    ("electricity_balance", "ru", "Я не могу посмотреть остаток на вашем счёте за электричество. Проверьте баланс официальным способом, который предоставляет ваш поставщик. Если вы назовёте организацию, я уточню, есть ли у нас подтверждённая инструкция для неё. Проверить состояние вашего счёта может официальная служба поддержки поставщика."),
    ("utility_payment", "uz", "Elektr, gaz, suv yoki isitish uchun xizmat ko‘rsatuvchingiz tasdiqlagan to‘lov kanalidan foydalaning. To‘lovni tasdiqlashdan oldin xizmat turi, shaxsiy hisob raqami va summani tekshiring, keyin chekni saqlang. Bu bot pul qabul qilmaydi va to‘lov o‘tkazmaydi."),
    ("utility_payment", "ru", "Для оплаты электричества, газа, воды или отопления используйте платёжный канал, подтверждённый вашим поставщиком. Перед подтверждением проверьте вид услуги, номер лицевого счёта и сумму, затем сохраните чек. Этот бот не принимает деньги и не проводит платежи."),
    ("payment_delay", "uz", "Chekni saqlang. To‘lov qilgan xizmatingizda operatsiya holati, xizmat turi va hisob raqamini tekshiring. Pul yechilgan, lekin kommunal hisobda ko‘rinmayotgan bo‘lsa, to‘lov xizmati va xizmat ko‘rsatuvchining rasmiy yordamiga murojaat qiling. Men tranzaksiyani tekshira olmayman va tushish muddatini tasdiqlay olmayman."),
    ("payment_delay", "ru", "Сохраните чек. В сервисе, через который вы платили, проверьте статус операции, вид услуги и номер лицевого счёта. Если деньги списаны, но платёж не отображается на коммунальном счёте, обратитесь в официальную поддержку платёжного сервиса и поставщика. Я не могу проверить транзакцию или подтвердить срок зачисления."),
    ("debt_check", "uz", "Men sizning qarzdorligingizni ko‘ra olmayman. Qaysi xizmat — elektr, gaz, suv yoki isitish — bo‘yicha tekshirmoqchisiz? Qarzdorlikni xizmat ko‘rsatuvchingiz taqdim etgan rasmiy usul orqali aniqlang. Summa bo‘yicha e’tirozingiz bo‘lsa, hisob-kitobni rasmiy yordam xizmatidan tushuntirishni so‘rang."),
    ("debt_check", "ru", "Я не могу посмотреть вашу задолженность. По какой услуге вы хотите её проверить: электричество, газ, вода или отопление? Уточните задолженность официальным способом, который предоставляет поставщик. Если вы не согласны с суммой, запросите разъяснение расчёта в его официальной службе поддержки."),
]


@pytest.fixture
def catalog():
    return load_catalog()


@pytest.fixture
def editable_kb(tmp_path):
    root = tmp_path / "knowledge_base"
    shutil.copytree(DEFAULT_KB_ROOT, root)
    return root


def edit_json(root, filename, change):
    path = root / filename
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize("item_id,language,expected", APPROVED_1_4)
def test_approved_faq_1_4_are_exact_and_present_in_kb(catalog, item_id, language, expected):
    item = catalog.faq_items[item_id]
    assert item.answer.text(language) == expected
    assert any(expected in catalog.document_texts[(key, language)] for key in item.source_ids)


def test_all_five_faq_and_all_four_utilities_have_both_languages(catalog):
    assert set(catalog.faq_items) == {
        "electricity_balance", "utility_payment", "payment_delay", "debt_check", "utility_issue"
    }
    assert set(catalog.utilities) == {"electricity", "gas", "water", "heating"}
    assert len(catalog.document_texts) == 20
    for document in catalog.documents.values():
        for language in ("uz", "ru"):
            assert "DEMO" in catalog.document_texts[(document.id, language)]


def test_menu_matching_handles_both_languages_and_apostrophe_variants(catalog):
    assert catalog.find_question("  To'lovni qanday amalga oshiraman? ") == ("faq", "utility_payment")
    assert catalog.find_question("📄 Как проверить задолженность?") == ("faq", "debt_check")


@pytest.mark.parametrize("text", ["salom", "/unknown", "gaz hidi", "мой вопрос", "private-card-number"])
def test_unmatched_free_text_does_not_invent_an_answer_or_classification(catalog, text):
    assert catalog.find_question(text) is None


def test_contacts_have_distinct_roles_and_sources(catalog):
    numbers = {entry.number: entry for entry in catalog.support.numbers}
    assert set(numbers) == {"101", "104", "112", "1154"}
    assert "Yong‘in" in numbers["101"].purpose.uz
    assert "Gaz" in numbers["104"].purpose.uz
    assert "dispetcherlik" in numbers["112"].purpose.uz
    assert "elektr" in numbers["1154"].purpose.uz
    assert all(entry.source_ids for entry in numbers.values())


@pytest.mark.parametrize("language", ["uz", "ru"])
def test_safety_sources_phone_roles_and_no_operator_wait(catalog, language):
    for item in catalog.support.safety:
        answer = catalog.format_support("safety", item.id, language)
        assert "https://" in answer
        assert "112" in answer
        assert ("kutmang" if language == "uz" else "Не ждите") in answer
        assert len(answer.encode("utf-16-le")) // 2 <= 4096
        if item.id != "electrical_wire":
            assert "1154" not in answer
    assert "104" in catalog.format_support("safety", "gas_leak", language)
    assert "101" in catalog.format_support("safety", "fire", language)


def test_gas_controls_and_water_do_not_enter_instruction_are_preserved(catalog):
    gas = catalog.safety["gas_leak"].answer
    assert "Imkon bo‘lsa gaz jo‘mragini yoping." in gas.uz
    assert "Xavfsiz bo‘lsa eshik va derazalarni oching." in gas.uz
    assert "Если это возможно, перекройте газовый кран." in gas.ru
    assert "Если это безопасно, откройте двери и окна." in gas.ru
    water = catalog.safety["water_electric"].answer
    assert "Elektrni o‘chirish uchun suvga kirmang" in water.uz
    assert "Не входите в воду, чтобы отключить электричество" in water.ru


def test_draft_answer_is_not_exposed(editable_kb):
    edit_json(editable_kb, "faq.json", lambda data: data["items"][0].update(status="draft"))
    catalog = load_catalog(editable_kb)
    assert catalog.find_question("Elektr hisobimda qancha pul bor?") is None


@pytest.mark.parametrize("filename,change", [
    ("faq.json", lambda d: d["items"][0]["answer"].pop("ru")),
    ("faq.json", lambda d: d["items"].append(d["items"][0])),
    ("faq.json", lambda d: d["items"][0].update(source_ids=["missing_document"])),
    ("faq.json", lambda d: d["items"][0]["answer"].update(uz="   ")),
    ("support.json", lambda d: d["safety"][0].update(source_ids=[])),
    ("support.json", lambda d: d["safety"][0].update(source_ids=["missing_source"])),
    ("index.json", lambda d: d["documents"][0]["files"].update(uz="../outside.md")),
    ("index.json", lambda d: d["documents"][0]["files"].update(uz=d["documents"][0]["files"]["ru"])),
    ("index.json", lambda d: d["sources"][0].update(url="http://example.org/unsafe")),
])
def test_invalid_content_is_rejected_safely(editable_kb, filename, change):
    edit_json(editable_kb, filename, change)
    with pytest.raises(KnowledgeBaseError):
        load_catalog(editable_kb)


def test_missing_kb_reports_actionable_error(tmp_path):
    with pytest.raises(KnowledgeBaseError, match="index.json"):
        load_catalog(tmp_path / "missing")


def test_missing_markdown_is_rejected(editable_kb):
    (editable_kb / "gas" / "issues.ru.md").unlink()
    with pytest.raises(KnowledgeBaseError, match="hujjatini"):
        load_catalog(editable_kb)


def test_malformed_json_does_not_echo_file_content(editable_kb):
    (editable_kb / "faq.json").write_text("{private-sensitive-content", encoding="utf-8")
    with pytest.raises(KnowledgeBaseError) as error:
        load_catalog(editable_kb)
    assert "private-sensitive-content" not in str(error.value)


def test_paths_are_independent_of_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert len(load_catalog().faq_items) == 5


def test_overlong_safety_response_is_rejected_before_startup(editable_kb):
    def change(data):
        data["safety"][0]["answer"]["uz"] = "🧯" * 2400
    edit_json(editable_kb, "support.json", change)
    with pytest.raises(KnowledgeBaseError, match="chegarasidan"):
        load_catalog(editable_kb)
