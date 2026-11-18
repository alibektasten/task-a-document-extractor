"""Deliberately bounded normalization; never infer missing business facts."""

import re
from datetime import date
from decimal import Decimal

NUM = r"(?:[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+|[0-9]+)(?:[.,][0-9]{1,2})?"
MONTHS = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4,
    "мая": 5, "июня": 6, "июля": 7, "августа": 8,
    "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
    "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4,
    "мамыр": 5, "маусым": 6, "шілде": 7, "тамыз": 8,
    "қыркүйек": 9, "қазан": 10, "қараша": 11, "желтоқсан": 12,
}
DATE = re.compile(
    r"(?<![\w.])(?:[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{4}|"
    r"[0-9]{1,2}\s+(?:" + "|".join(MONTHS) + r")\s+[0-9]{4})(?![\w])",
    re.IGNORECASE,
)
CURRENCY = re.compile(r"\b(KZT|USD|EUR|тенге|теңге|тг|доллар(?:ов|а)?|евро)\b|₸|€", re.I)


def number(raw: str) -> float:
    raw = raw.strip()
    if not re.fullmatch(NUM, raw):
        raise ValueError("unsupported number")
    value = Decimal(re.sub(r"[\s\u00a0\u202f]", "", raw).replace(",", "."))
    if value > 1_000_000_000_000:
        raise ValueError("number exceeds supported range")
    return float(value)


def calendar_date(raw: str) -> str:
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        return date.fromisoformat(raw).isoformat()
    if "." in raw:
        day, month, year = map(int, raw.split("."))
    else:
        day, month_name, year = raw.lower().split()
        day, month, year = int(day), MONTHS[month_name], int(year)
    return date(year, month, day).isoformat()


def currencies(raw: str) -> list[str]:
    result = []
    for match in CURRENCY.finditer(raw):
        token = match.group().lower()
        value = "USD" if token.startswith(("usd", "доллар")) else (
            "EUR" if token in ("eur", "евро", "€") else "KZT"
        )
        if value not in result:
            result.append(value)
    return result


RU_UNITS = dict(zip(
    "ноль один два три четыре пять шесть семь восемь девять".split(), range(10)
)) | {"одна": 1, "одно": 1, "две": 2}
RU_TEENS = dict(zip(
    "десять одиннадцать двенадцать тринадцать четырнадцать пятнадцать шестнадцать семнадцать восемнадцать девятнадцать".split(), range(10, 20)
))
RU_TENS = dict(zip("двадцать тридцать сорок пятьдесят шестьдесят семьдесят восемьдесят девяносто".split(), range(20, 100, 10)))
RU_HUNDREDS = dict(zip("сто двести триста четыреста пятьсот шестьсот семьсот восемьсот девятьсот".split(), range(100, 1000, 100)))
KZ_UNITS = dict(zip("нөл бір екі үш төрт бес алты жеті сегіз тоғыз".split(), range(10)))
KZ_TENS = dict(zip("он жиырма отыз қырық елу алпыс жетпіс сексен тоқсан".split(), range(10, 100, 10)))
SCALES = {"тысяча": 1000, "тысячи": 1000, "тысяч": 1000, "мың": 1000,
          "миллион": 1_000_000, "миллиона": 1_000_000, "миллионов": 1_000_000}


def _group(tokens: list[str]) -> int:
    """Parse one grammatical RU or KZ number group below 1000."""
    remaining = tokens.copy()
    value = 0
    if remaining and remaining[0] in RU_HUNDREDS:
        value += RU_HUNDREDS[remaining.pop(0)]
    elif len(remaining) >= 2 and remaining[0] in KZ_UNITS and remaining[1] == "жүз":
        value += KZ_UNITS[remaining.pop(0)] * 100
        remaining.pop(0)
    elif remaining and remaining[0] == "жүз":
        value = 100
        remaining.pop(0)
    tens = RU_TENS | KZ_TENS
    units = RU_UNITS | KZ_UNITS
    if remaining and remaining[0] in RU_TEENS:
        value += RU_TEENS[remaining.pop(0)]
        if remaining:
            raise ValueError("invalid word-number grammar")
    else:
        if remaining and remaining[0] in tens:
            value += tens[remaining.pop(0)]
        if remaining and remaining[0] in units:
            value += units[remaining.pop(0)]
    if remaining or not tokens:
        raise ValueError("unsupported number words")
    return value


def money(raw: str) -> float:
    raw = raw.strip().rstrip(".").strip()
    numeric = re.fullmatch(rf"({NUM})(?:\s*(?:{CURRENCY.pattern}))?", raw, re.I)
    if numeric:
        return number(numeric.group(1))
    words = re.fullmatch(
        r"(.+?)\s+(?:тенге|теңге)(?:\s+([0-9]{1,2})\s+(?:тиын|тиынов))?", raw, re.I
    )
    if not words:
        raise ValueError("unsupported amount")
    tokens = words.group(1).lower().split()
    total, group, last_scale = 0, [], 1_000_000_000
    for token in tokens:
        if token in SCALES:
            scale = SCALES[token]
            if scale >= last_scale:
                raise ValueError("invalid scale order")
            total += (_group(group) if group else 1) * scale
            group, last_scale = [], scale
        else:
            group.append(token)
    if group:
        total += _group(group)
    return float(Decimal(total) + Decimal(words.group(2) or 0) / 100)
