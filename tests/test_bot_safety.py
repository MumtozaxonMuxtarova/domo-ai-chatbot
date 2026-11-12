"""Phrase guard routes to approved answers; it is not a complete risk detector."""

import pytest

from app.bot.safety import detect_safety


@pytest.mark.parametrize("text,item_id", [
    ("Uyda gaz hidi bor", "gas_leak"),
    ("Gaz sizib chiqyapti", "gas_leak"),
    ("В квартире пахнет газом", "gas_leak"),
    ("Чувствую запах газа", "gas_leak"),
    ("Открыт кран, утечка газа", "gas_leak"),
    ("Ochiq elektr simi bor", "electrical_wire"),
    ("Sim uzilib tushgan", "electrical_wire"),
    ("Meni tok urdi", "electrical_wire"),
    ("Розетка искрит", "electrical_wire"),
    ("Ударило током", "electrical_wire"),
    ("Розетка не искрит, но провод оголён", "electrical_wire"),
    ("Газом не пахнет, но оборванный провод лежит во дворе", "electrical_wire"),
    ("Gaz hidi yo‘q, lekin ochiq sim bor", "electrical_wire"),
    ("Uyda yong‘in boshlandi", "fire"),
    ("Uy yonayapti", "fire"),
    ("Yong‘in yo‘q, lekin rozetkadan tutun chiqyapti", "fire"),
    ("Начался пожар", "fire"),
    ("Из розетки идёт дым", "fire"),
    ("Suv rozetkaga tegdi", "water_electric"),
    ("Elektr jihozini suv bosdi", "water_electric"),
    ("Elektrni o‘chirish uchun suvga kirsam bo‘ladimi?", "water_electric"),
    ("Вода попала в розетку", "water_electric"),
    ("Электроприбор стоит в воде", "water_electric"),
    ("Можно зайти в воду и выключить электричество?", "water_electric"),
    ("Gaz hidi bor va rozetkadan tutun chiqyapti", "gas_leak"),
    ("Gaz hidi bor va yong‘in boshlandi", "fire"),
    ("Пахнет газом и начался пожар", "fire"),
    ("Газ утекает", "gas_leak"),
])
def test_clear_hazard_and_local_negation(text, item_id):
    assert detect_safety(text) == item_id


@pytest.mark.parametrize("text", [
    "Gaz hidi yo‘q, faqat gaz kelmayapti", "Запаха газа нет, газ отключён",
    "Розетка не искрит", "Пожара нет", "Yong‘in yo‘q",
    "Elektr uchun qanday to‘layman?", "Suv va elektr hisoblari haqida savolim bor",
    "Что означает пожарная безопасность?", "Gaz bosimi pasaydi", "Suv kelmayapti",
    "Gaz sizga kerakmi?", "Gaz sizlarda bormi?", "Gaz sizdan keladimi?",
])
def test_ordinary_utility_and_negated_hazard_are_not_emergencies(text):
    assert detect_safety(text) is None
