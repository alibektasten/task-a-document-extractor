"""Validate proposals, verify evidence, resolve conflicts, validate the result."""

from dataclasses import dataclass

from pydantic import ValidationError

from .parsing import Hit, buyer_lines, parse_line
from .providers import MAX_RESPONSE_BYTES, Provider, ProviderError
from .schema import FIELDS, Document, Proposal, empty_document

MAX_INPUT_BYTES = 100_000
MAX_LINES = 2000
# The model must not hide a contradiction by selecting only a convenient line.
AUDIT_FIELDS = ("doc_date", "total_amount", "currency", "supplier_bin", "vat_amount")


@dataclass(frozen=True)
class ExtractionResult:
    document: Document
    failed: bool = False
    attempts: int = 0


def _distinct(hits: list[Hit]) -> list:
    values = []
    for hit in hits:
        if hit.value not in values:
            values.append(hit.value)
    return values


def _resolve(field: str, hits: list[Hit], warnings: list[str]):
    if not hits:
        return ("unknown" if field == "doc_type" else None), 0.0
    distinct = _distinct(hits)
    if len(distinct) > 1:
        warnings.append(f"CONFLICT:{field}: multiple distinct values; applied documented selection rule")
    if field in ("supplier_bin", "supplier_name", "currency", "vat_amount", "doc_type") and len(distinct) > 1:
        return ("unknown" if field == "doc_type" else None), 0.0
    if field == "doc_date":
        hits = [hit for hit in hits if hit.priority > 0]
        if not hits:
            warnings.append("DATE_NOT_ISSUE: only non-issue dates found; left null")
            return None, 0.0
    # Python max is stable: first source occurrence wins among equal priorities.
    chosen = max(hits, key=lambda hit: hit.priority)
    return chosen.value, min(chosen.confidence, 0.5) if len(distinct) > 1 else chosen.confidence


def extract(text: str, provider: Provider) -> ExtractionResult:
    if len(text.encode("utf-8")) > MAX_INPUT_BYTES or len(text.splitlines()) > MAX_LINES:
        return ExtractionResult(empty_document("INPUT_TOO_LARGE: limit is 100000 UTF-8 bytes and 2000 lines"), failed=True)
    if not text.strip():
        return ExtractionResult(empty_document("EMPTY_DOCUMENT: no extractable text"))
    proposal = None
    warnings: list[str] = []
    feedback = None
    for attempt in (1, 2):
        try:
            raw = provider.generate(text, feedback)
            if len(raw.encode("utf-8")) > MAX_RESPONSE_BYTES:
                raise ProviderError("response exceeds size limit")
            proposal = Proposal.model_validate_json(raw)
            break
        except ValidationError as exc:
            # Redact the rejected input; only schema error locations/types go back.
            feedback = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors(include_input=False)[:8])
        except ProviderError:
            return ExtractionResult(empty_document("PROVIDER_ERROR: extraction backend unavailable or invalid transport response"), failed=True, attempts=attempt)
    if proposal is None:
        return ExtractionResult(empty_document("LLM_VALIDATION_FAILED: invalid response after 2 attempts; all fields abstained"), failed=True, attempts=2)
    if attempt == 2:
        warnings.append("LLM_RETRY: first response failed schema validation; second response accepted")

    lines = text.splitlines()
    buyers = buyer_lines(lines)
    selected = {(e.line, e.field) for e in proposal.evidence}
    for index, line in enumerate(lines, 1):
        for field in AUDIT_FIELDS:
            parsed = parse_line(field, line)
            if parsed.hits or parsed.warnings:
                selected.add((index, field))
    hits: dict[str, list[Hit]] = {field: [] for field in FIELDS}
    for index, field in sorted(selected):
        if index > len(lines):
            warnings.append(f"UNSUPPORTED_EVIDENCE:{field}: source line {index} does not exist")
            continue
        if index in buyers and field in ("supplier_name", "supplier_bin"):
            continue
        parsed = parse_line(field, lines[index - 1])
        if not parsed.hits and not parsed.warnings:
            warnings.append(f"UNSUPPORTED_EVIDENCE:{field}: source line {index} has no supported evidence")
        hits[field].extend(parsed.hits)
        warnings.extend(parsed.warnings)

    data = empty_document().model_dump()
    for field in FIELDS:
        if field == "line_items":
            data[field] = [hit.value for hit in hits[field]]
            data["field_confidence"][field] = 0.95 if hits[field] else 0.0
        else:
            data[field], data["field_confidence"][field] = _resolve(field, hits[field], warnings)
    data["warnings"] = list(dict.fromkeys(warnings))
    try:
        document = Document.model_validate(data)
    except ValidationError:
        # An internal normalizer bug must never leak an invalid business result.
        return ExtractionResult(empty_document("OUTPUT_VALIDATION_FAILED: normalized result rejected; all fields abstained"), failed=True, attempts=attempt)
    return ExtractionResult(document, attempts=attempt)
