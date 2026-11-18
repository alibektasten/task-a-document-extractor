"""Parse supported evidence lines. Unknown or damaged formats cause abstention."""

import re
from dataclasses import dataclass, field
from typing import Any

from .normalize import CURRENCY, DATE, NUM, calendar_date, currencies, money, number

DOC_HEADER = re.compile(r"^(?:сч[её]т(?:\s+на\s+оплату|-фактура)?|шот[- ]фактура|акт\b|коммерческое предложение)", re.I)
BUYER = re.compile(r"^(?:покупатель|заказчик|получатель|сатып алушы)\b", re.I)
SUPPLIER = re.compile(r"^(?:поставщик|исполнитель|жеткізуші)\s*:\s*(.+)$", re.I)
TOTAL = re.compile(r"^(всего к оплате|к оплате|итого(?: к оплате)?|общая сумма|жалпы сомасы)\s*:\s*(.+)$", re.I)


@dataclass(frozen=True)
class Hit:
    value: Any
    priority: int = 0
    confidence: float = 0.95


@dataclass
class Parsed:
    hits: list[Hit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def buyer_lines(lines: list[str]) -> set[int]:
    """Do not accidentally attribute a buyer's separate BIN line to the supplier."""
    result = set()
    buyer = False
    for index, line in enumerate(lines, 1):
        stripped = line.strip()
        if BUYER.match(stripped):
            buyer = True
        elif SUPPLIER.match(stripped) or DOC_HEADER.match(stripped):
            buyer = False
        if buyer:
            result.add(index)
    return result


def _line_item(line: str) -> dict | None:
    # A table needs tab or >=2-space column boundaries; single spaces group digits.
    cells = re.split(r"\t+| {2,}", line.strip())
    if len(cells) in (3, 4):
        try:
            return {"name": cells[0], "qty": None if cells[1] == "-" else number(cells[1]),
                    "price": None if cells[2] == "-" else money(cells[2])}
        except ValueError:
            return None
    service = re.fullmatch(rf"(.+?)\s+[-—–]\s+({NUM})\s*(?:ед\.?|шт\.?)\s+[-—–]\s+(.+)", line)
    if service:
        return {"name": service.group(1), "qty": number(service.group(2)),
                "price": money(service.group(3))}
    offer = re.fullmatch(r"[-•]\s+(.+?)\s+[—–-]\s+(.+)", line)
    if offer:
        return {"name": offer.group(1), "qty": None,
                "price": None if offer.group(2).lower() in ("не указана", "по запросу") else money(offer.group(2))}
    return None


def parse_line(field_name: str, raw: str) -> Parsed:
    line = raw.strip()
    lower = line.lower()
    out = Parsed()
    if not line:
        return out
    if field_name == "doc_type":
        if re.match(r"^(?:сч[её]т\b|шот[- ]фактура\b)", lower):
            out.hits.append(Hit("invoice"))
        elif lower.startswith("коммерческое предложение"):
            out.hits.append(Hit("commercial_offer"))
        elif re.match(r"^акт\b", lower):
            out.hits.append(Hit("act"))
    elif field_name == "supplier_name":
        supplier = SUPPLIER.match(line)
        company = re.match(r"^от компании\s+[«\"](.+?)[»\"]\s*$", line, re.I)
        if supplier:
            out.hits.append(Hit(supplier.group(1)))
        elif company:
            out.hits.append(Hit(company.group(1)))
        elif re.match(r"^(?:ТОО|ЖШС|ИП|LLP|LLC)\s+[«\"]", line, re.I):
            out.hits.append(Hit(line))
    elif field_name == "supplier_bin":
        match = re.match(r"^(?:(?:поставщик|исполнитель)\s+)?(?:БСН\s*/\s*БИН|БИН|БСН)\s*:?\s*(\S+)\s*$", line, re.I)
        if match:
            if re.fullmatch(r"[0-9]{12}", match.group(1)):
                out.hits.append(Hit(match.group(1)))
            else:
                out.warnings.append("INVALID_BIN: ambiguous OCR or non-12-digit BIN; left null")
    elif field_name == "doc_number" and DOC_HEADER.match(line):
        match = re.search(r"№\s*([A-Za-zА-Яа-я0-9][\w./-]*)", line)
        if match:
            out.hits.append(Hit(match.group(1)))
    elif field_name == "doc_date":
        # Dates without issue context remain visible for conflicts, but are not selected.
        issue = bool(DOC_HEADER.match(line) or re.match(r"^(?:составлено|дата документа|дата составления)\b", lower))
        expiry = bool(re.search(r"действительно до|срок|оплатить до|дейін", lower))
        priority = 2 if issue and not expiry else 0
        for match in DATE.finditer(line):
            try:
                out.hits.append(Hit(calendar_date(match.group()), priority))
            except ValueError:
                out.warnings.append("INVALID_DATE: impossible calendar date; ignored")
    elif field_name == "currency":
        # Do not read currency symbols from arbitrary prose or prompt instructions.
        if TOTAL.match(line) or re.match(r"^(?:валюта|валютасы)\s*:", lower) or re.match(r"^[-•]\s", line) or len(re.split(r"\t+| {2,}", line)) in (3, 4):
            out.hits.extend(Hit(value) for value in currencies(line))
    elif field_name == "total_amount":
        match = TOTAL.match(line)
        if match:
            try:
                priority = 2 if "оплате" in match.group(1).lower() else 1
                out.hits.append(Hit(money(match.group(2)), priority, 0.90 if re.search(r"[а-яәіңғүұқөһ]", match.group(2), re.I) and not re.match(r"[0-9]", match.group(2)) else 0.95))
            except ValueError:
                out.warnings.append("INVALID_TOTAL: unsupported or damaged amount; left null")
    elif field_name == "vat_amount":
        if re.match(r"^(?:ндс|без ндс|ққс)\b", lower):
            if re.search(r"не облагается|без ндс|освобожден|салынбайды", lower):
                out.warnings.append("VAT_EXEMPT: no numeric VAT amount stated; left null")
            else:
                match = re.match(r"^(?:ндс|ққс)(?:\s+[0-9]+(?:[.,][0-9]+)?%)?\s*:\s*(.+)$", line, re.I)
                if match:
                    try:
                        out.hits.append(Hit(money(match.group(1))))
                    except ValueError:
                        out.warnings.append("INVALID_VAT: no supported numeric VAT amount")
                else:
                    out.warnings.append("VAT_NOT_STATED: a rate does not establish a VAT amount")
    elif field_name == "line_items":
        if not (TOTAL.match(line) or DOC_HEADER.match(line) or re.match(r"^(?:ндс|ққс|наименование)\b", lower)):
            try:
                item = _line_item(line)
                if item:
                    out.hits.append(Hit(item))
            except ValueError:
                out.warnings.append("INVALID_LINE_ITEM: unsupported numeric cells; row ignored")
    return out
