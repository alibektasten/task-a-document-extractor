"""Frozen-gold evaluation. Never writes or derives expected answers from predictions."""

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pydantic import ValidationError

from .cli import add_backend_arguments, make_provider
from .pipeline import extract
from .schema import FIELDS, Document

PUBLIC_FIELDS = (*FIELDS, "field_confidence", "warnings")
NULLABLE_FIELDS = ("supplier_name", "supplier_bin", "doc_number", "doc_date", "currency", "total_amount", "vat_amount")


@dataclass
class Metric:
    correct: int = 0
    total: int = 0
    hallucinations: int = 0
    omissions: int = 0
    wrong_values: int = 0
    populated_correct: int = 0
    populated_total: int = 0

    def observe(self, expected, predicted, nullable: bool = False, matched: bool = True) -> None:
        self.total += 1
        self.correct += matched and expected == predicted
        if expected is not None:
            self.populated_total += 1
            self.populated_correct += matched and expected == predicted
        if nullable:
            self.hallucinations += expected is None and predicted is not None
            self.omissions += expected is not None and predicted is None
        self.wrong_values += expected is not None and predicted is not None and expected != predicted

    def report(self) -> dict:
        return asdict(self) | {
            "accuracy": self.correct / self.total if self.total else None,
            "populated_accuracy": self.populated_correct / self.populated_total if self.populated_total else None,
        }


def score_pairs(pairs: list[tuple[str, Document, Document]], failures: list[str] | None = None) -> dict:
    metrics = {field: Metric() for field in (*PUBLIC_FIELDS, "line_items[].name", "line_items[].qty", "line_items[].price")}
    differences = []
    exact = 0
    extra_items = missing_items = 0
    for identifier, expected_doc, predicted_doc in pairs:
        expected, predicted = expected_doc.model_dump(), predicted_doc.model_dump()
        mismatch = {}
        for field in PUBLIC_FIELDS:
            left, right = expected[field], predicted[field]
            if field == "warnings":
                left, right = sorted(left), sorted(right)
            metrics[field].observe(left, right, field in NULLABLE_FIELDS)
            if left != right:
                mismatch[field] = {"expected": left, "predicted": right}
        exact += all(expected[field] == predicted[field] for field in FIELDS)
        left_items, right_items = expected["line_items"], predicted["line_items"]
        missing_items += max(0, len(left_items) - len(right_items))
        extra_items += max(0, len(right_items) - len(left_items))
        for index in range(max(len(left_items), len(right_items))):
            left = left_items[index] if index < len(left_items) else None
            right = right_items[index] if index < len(right_items) else None
            for key in ("name", "qty", "price"):
                # Unmatched rows are collection errors, not null-field errors.
                metrics[f"line_items[].{key}"].observe(
                    left[key] if left else None, right[key] if right else None,
                    nullable=left is not None and right is not None and key != "name",
                    matched=left is not None and right is not None,
                )
        if mismatch:
            differences.append({"id": identifier, "fields": mismatch})
    return {
        "documents": len(pairs), "exact_business_documents": exact,
        "exact_business_accuracy": exact / len(pairs) if pairs else None,
        "fields": {field: metric.report() for field, metric in metrics.items()},
        "hallucinations": sum(m.hallucinations for m in metrics.values()),
        "omissions": sum(m.omissions for m in metrics.values()),
        "extra_line_items": extra_items, "missing_line_items": missing_items,
        "pipeline_failures": failures or [], "differences": differences,
    }


def evaluate(data_dir: Path, provider) -> dict:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("manifest must be a non-empty list")
    pairs, failures, seen = [], [], set()
    for case in manifest:
        identifier = case["id"]
        if not isinstance(identifier, str) or not identifier or Path(identifier).name != identifier or identifier in seen:
            raise ValueError("invalid or duplicate case id")
        seen.add(identifier)
        gold = Document.model_validate_json((data_dir / "gold" / f"{identifier}.json").read_text(encoding="utf-8"))
        text = (data_dir / "documents" / f"{identifier}.txt").read_text(encoding="utf-8")
        result = extract(text, provider)
        if result.failed:
            failures.append(identifier)
        pairs.append((identifier, gold, result.document))
    return score_pairs(pairs, failures)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run all frozen-gold cases and report errors separately")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--report", type=Path, help="Also write a machine-readable report")
    add_backend_arguments(parser)
    args = parser.parse_args(argv)
    provider = make_provider(args, parser)
    try:
        report = evaluate(args.data_dir, provider)
    except (OSError, ValueError, ValidationError, KeyError, TypeError) as exc:
        parser.exit(2, f"Evaluation input error: {type(exc).__name__}; check corpus and gold schema.\n")
    report["backend"] = args.backend
    print(f"Backend: {args.backend} | Documents: {report['documents']}")
    print(f"{'Field':25} {'Exact':>9} {'Accuracy':>9} {'Halluc.':>8} {'Omit.':>7} {'Wrong':>7}")
    for field, values in report["fields"].items():
        fraction = f"{values['correct']}/{values['total']}"
        accuracy = f"{values['accuracy']:.1%}" if values['accuracy'] is not None else "n/a"
        print(f"{field:25} {fraction:>9} {accuracy:>9} {values['hallucinations']:8} {values['omissions']:7} {values['wrong_values']:7}")
    print(f"Hallucinations: {report['hallucinations']} | Omissions: {report['omissions']}")
    print(f"Extra items: {report['extra_line_items']} | Missing items: {report['missing_line_items']}")
    print(f"Exact business documents: {report['exact_business_documents']}/{report['documents']}")
    print(f"Pipeline failures: {len(report['pipeline_failures'])}")
    for mismatch in report["differences"]:
        print(f"Mismatch {mismatch['id']}: {', '.join(mismatch['fields'])}")
    if args.report:
        try:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except OSError:
            parser.exit(2, "Cannot write evaluation report.\n")
    return 1 if report["differences"] or report["pipeline_failures"] else 0
