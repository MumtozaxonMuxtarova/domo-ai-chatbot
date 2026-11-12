"""Conservative phrase routing to existing approved safety answers, not diagnosis."""

import re
import unicodedata


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    value = "".join(char for char in value if unicodedata.category(char) != "Cf")
    return value.translate(str.maketrans({"‘": "'", "’": "'", "ʻ": "'", "ʼ": "'", "`": "'"}))


def _positive(text: str, pattern: str) -> bool:
    for match in re.finditer(pattern, text):
        before = text[max(0, match.start() - 30):match.start()]
        after = text[match.end():match.end() + 30]
        if re.search(r"\b(?:не|нет|без)\s*$", before):
            continue
        if re.match(r"\s*(?:yo'q|emas|mavjud emas|нет|отсутствует)\b", after):
            continue
        if re.search(r"\bне\s+", match.group()):
            continue
        return True
    return False


# Narrow relationships avoid treating utility billing/payment words as hazards.
_RULES = (
    ("fire", (
        r"\byong'in\b", r"\b(?:uy|xona|bino)\w*\s+yon(?:ayap|yap|moqda)\w*",
        r"\bпожар\b", r"\bгорит\s+(?:квартир|дом|комнат|розетк)\w*",
        r"\b(?:квартир|дом|комнат|розетк)\w*\s+горит\b",
    )),
    ("gas_leak", (
        r"\bgaz(?:ning)?\s+hidi\b", r"\bgaz\s+siz(?:ib|ish|moqda|ayotgan|yap|ayap|di|adi)\w*",
        r"\bgaz\s+chiqib\s+ket\w*",
        r"\bпахнет\s+газом\b", r"\bзапах\w*\s+газа\b", r"\bутечк\w*\s+газа\b",
        r"\bгаз\s+утекает\b",
    )),
    ("water_electric", (
        r"\bsuv\s+.{0,35}(?:rozetka|sim|elektr|jihoz)\w*.{0,25}(?:teg|yet|tush|bos|to'kil)\w*",
        r"\b(?:elektr|rozetka|sim|jihoz)\w*.{0,35}suv\s+(?:bos\w*|ichida|ga\s+tush\w*)",
        r"\belektr\w*.{0,30}o'chir\w*.{0,30}suvga\s+kir\w*",
        r"\bвод[аы]\s+.{0,25}(?:попал|достиг|затоп)\w*.{0,30}(?:розет|элект|провод)\w*",
        r"\b(?:электроприбор|розетк|провод)\w*.{0,30}(?:в\s+воде|затоп)\w*",
        r"\b(?:зайти|войти|зайду)\s+в\s+воду.{0,35}(?:отключ|выключ)\w*.{0,20}(?:электр|свет)\w*",
    )),
    ("fire", (
        r"\b(?:rozetka|sim|uy|xona)\w*.{0,20}tutun\s+chiq\w*",
        r"\bиз\s+(?:розетк|комнат|провод)\w*.{0,20}(?:идет\s+)?дым\b",
    )),
    ("electrical_wire", (
        r"\b(?:ochiq|uzilgan|uzilib\s+tushgan)\s+(?:elektr\s+)?sim\w*",
        r"\bsim\w*\s+(?:uzilib|uzilgan|ochiq)\w*",
        r"\b(?:rozetka|sim|elektr)\w*.{0,20}uchqun\s+chiq\w*",
        r"\btok\s+ur(?:di|yap|gan|moqda)\w*", r"\belektr\s+xavfi\b",
        r"\b(?:оголен|оборван|поврежден)\w*\s+(?:электрическ\w+\s+)?провод\w*",
        r"\bпровод\w*\s+(?:оголен|оборван|поврежден)\w*",
        r"\b(?:розетк|провод)\w*.{0,15}искр\w*",
        r"\b(?:ударил\w*|бьет)\s+током\b",
    )),
)


def detect_safety(text: str) -> str | None:
    normalized = _normalize(text)
    for item_id, patterns in _RULES:
        if any(_positive(normalized, pattern) for pattern in patterns):
            return item_id
    return None
