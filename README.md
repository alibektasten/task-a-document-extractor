# DocGuard · Task A

An evidence-grounded CLI for extracting invoices, commercial offers, and acts into the assignment's fixed JSON schema. It favors an explicit `null` over an unsupported business fact.

**Runs without an API key.** The default backend is an openly labelled, deterministic rule-based mock. The extraction pipeline, validation, conflict handling, and evaluation are real. An optional Ollama adapter uses the same contracts; it has transport tests but has not been evaluated against a live model.

## Run from a clean checkout

Prerequisite: **Python 3.11 or 3.12** with `venv` and `pip` (verified locally with Python 3.12). The commands below use `python3.12`; use `python3.11` if that is your installed version. Internet is needed only to install dependencies; the default backend then works offline.

After cloning the repository or extracting the archive, open a terminal inside `task-a-document-extractor` and run:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install --no-deps -e .
python -m pip check
python -m docguard extract data/documents/01_invoice.txt
```

On Windows PowerShell, create the environment with `py -3.12 -m venv .venv` and use `.venv\Scripts\Activate.ps1`; the remaining `python` commands are identical. Windows is not locally verified.

No environment variables, database, paid API, or Docker daemon are required.

```bash
# Read UTF-8 text from stdin; stdout contains only the JSON result.
cat data/documents/03_kazakh_ocr.txt | python -m docguard extract -

# Run tests and all annotated examples.
python -m unittest discover -s tests -v
python eval.py

# Equivalent shortcuts, with the virtual environment active.
make test
make eval
make check

# Save a detailed evaluation report or export the output schema.
python eval.py --report reports/eval.json
python -m docguard schema > reports/output.schema.json
```

The installed `docguard` command is also available, for example `docguard extract data/documents/01_invoice.txt`.
On macOS/Linux, after installation you can also run `make PYTHON=.venv/bin/python demo` directly from the project folder without activating the environment. This is a CLI: each command prints its result and exits; there is no web server to keep running.

## What happens to a document

```text
UTF-8 text
  → evidence provider (mock / Ollama / replay)
  → strict Proposal validation; one retry on invalid model JSON
  → source-line verification + deterministic contradiction scan
  → bounded normalization and explicit selection rules
  → strict Document validation
  → fixed-schema JSON
```

The provider returns only field names and **1-based source line numbers**, not business values. For example, `{"evidence":[{"field":"supplier_bin","line":2}]}` points at a line that still has to match a supported BIN label and contain exactly 12 ASCII digits. A fabricated line, an unrelated number, a buyer's BIN, or an ambiguous OCR token is not accepted as supplier evidence.

`MockProvider` scans the actual input with the documented parsers; it does not read document filenames, fixture identifiers, expected JSON, or the evaluation corpus. Ollama can select evidence, but normalization remains deliberately bounded: switching backends does not make this an unrestricted document parser. An independent safety scan checks supported date, total, currency, BIN, and VAT lines so a model cannot hide these contradictions by omitting a line.

## Interpretation and conflict rules

| Field or situation | Rule |
| --- | --- |
| Missing scalar | `null`; unknown document type is `unknown`; absent items are `[]`. Never use today's date or retrieve identifiers from a company name. |
| Document type | Read the heading, not the number prefix. `Шот-фактура № AKT-09` is an `invoice`. Conflicting recognized types give `unknown` with a warning. |
| Supplier | Preserve the stated legal form/name; remove only the wrapper `от компании «…»`. Preserve bilingual names as written. Labelled buyer sections are excluded. Conflicting supplier names or valid BINs give `null`. |
| BIN | Exactly 12 ASCII digits, including leading zeros. No registry lookup, checksum assertion, or substitution of `O/0`, `l/1`. Document 3's damaged BIN stays `null`. |
| Dates | Parse real calendar dates: dotted day-month-year, ISO, or supported Russian/Kazakh month names. Prefer the first explicitly labelled issue date or heading date. The closest preceding role marker distinguishes issue, expiry, and referenced contract dates, including on the same line. An expiry-only or contract-only date never becomes `doc_date`. Different recognized dates produce a warning, including issue versus expiry. |
| Total | Explicit `Всего к оплате`, `К оплате`, or `Итого к оплате` outranks ordinary `Итого`/`Жалпы сомасы`. At equal priority, the first occurrence in source order wins. Different total-labelled amounts always produce a warning, including subtotal versus payable. |
| Currency | Only explicit supported currency evidence in a total, a parsed item's monetary cells, or a currency label. Currency words in item names are not payment evidence. KZT/USD/EUR are supported; no default KZT or ambiguous `$` interpretation. Conflicting currencies give `null`, while a separately explicit numeric total remains available. |
| VAT | Extract only an explicit numeric amount. `НДС 16%`, `Без НДС`, and `НДС не облагается` do not imply a numeric amount; return `null` with a warning. Explicit `НДС: 0` is zero. Conflicting numeric VAT amounts give `null`. |
| Items | Source order is preserved, including identical repeated rows. Never assume quantity 1 or derive price from a line total. Supported formats: table columns separated by tabs or at least two spaces, service rows `name - qty ед. - price`, and offer bullets `- name — price`. `-` in numeric table cells and `по запросу`/`не указана` in an offer price mean `null`. |
| Amounts in words | Normalize the explicit Russian/Kazakh amount in bounded supported grammar, including numeric tiyn. This is text normalization, not summing items or calculating VAT. Unsupported wording stays `null`. |
| Confidence | Heuristics, **not calibrated probabilities**: 0 for abstention; 0.95 for supported direct evidence; 0.90 for word amounts; at most 0.50 when selecting among conflicting values. Every extraction field has an entry. |

For supplied document 1, the total is **186180**, VAT is **25680**, and the differing `Итого` value is flagged. For supplied document 2, the issue date is **2026-11-05**, total and VAT remain **null**, and the expiry date is flagged as distinct. For document 3, the total is **340000**, the date is **2026-10-09**, and BIN and VAT stay **null**.

## Invalid model responses and operational errors

Reproduce a genuinely invalid response through the normal pipeline:

```bash
python -m docguard extract data/documents/01_invoice.txt \
  --backend replay --response-file examples/invalid-response.json
```

Expected behavior: two schema-validation attempts, then valid output JSON with `doc_type: "unknown"`, all nullable fields `null`, `line_items: []`, zero confidences, and an `LLM_VALIDATION_FAILED` warning. The process exits **2**. The system does not silently switch to the mock backend. A successful retry adds `LLM_RETRY`; redacted error locations/types are supplied as repair feedback.

Operational failures (missing file, bad UTF-8, provider failure, oversized input) also produce the fixed JSON schema and exit 2. Invalid normalized output fails closed with `OUTPUT_VALIDATION_FAILED`. A provider connection failure is not retried. Unsupported individual evidence is dropped with a warning, while supported fields can still succeed. Empty text is a valid abstention with `EMPTY_DOCUMENT` and exit 0. CLI usage errors use argparse's stderr message and exit 2 rather than an extraction JSON result.

Limits: 100,000 UTF-8 input bytes, 2,000 lines, 5,000 evidence references, 2 MB provider response, and a 60-second Ollama request timeout per attempt. Supported numeric values are nonnegative and at most 10^12. Logs/repair feedback do not echo document contents or raw rejected responses; requested output JSON necessarily contains extracted document data.

## Evaluation

The corpus has **14 documents: the 3 supplied examples and 11 authored examples**, each with a complete, separately authored gold JSON. Nine of the authored examples are labelled hard; they cover missing fields, word amounts, bilingual text, OCR damage, competing dates/totals/currencies, buyer-versus-supplier details, and instructions embedded in document text. See [the corpus guide](data/README.md).

`python eval.py` runs every manifest entry, validates every gold and prediction, and prints:

- Exact accuracy for every top-level output field and each line-item subfield.
- **Hallucinations:** expected `null`, predicted non-null.
- **Omissions:** expected non-null, predicted `null`.
- Wrong non-null values, extra/missing item rows, and failed pipeline runs separately.

Numeric JSON values compare numerically (100 equals 100.0); strings compare exactly; warning order is ignored; items are aligned by source position. Null mistakes are counted over nullable scalar fields and qty/price of matched item rows, without double-counting the enclosing array. Unmatched rows are collection errors, not explicit-null errors, and every leaf in an unmatched row is scored incorrect even if the expected leaf was null. The detailed report also includes accuracy restricted to populated gold values, per-document mismatches, and backend identity. `unknown` is a document-type label, not a null.

Exit codes: **0** = every expected output matches; **1** = differences or pipeline failures; **2** = invalid corpus, CLI usage, or report-writing failure. Bad gold data stops evaluation rather than disappearing from the denominator.

The checked-in baseline result is **14/14 exact business documents, 0 hallucinations, 0 omissions**, and all metadata fields match. This is a small, author-designed regression set, not a blind benchmark or a claim of production/model accuracy. Unit tests inject controlled errors to verify the evaluator's counters and exercise new values outside the corpus. See [verification details](docs/VERIFICATION.md) and [the full baseline report](docs/evaluation-baseline.json).

## Optional live Ollama backend

Install and run Ollama separately and pull an instruction model of your choice. No model is automatically installed and no network call occurs in default mode. Use the exact locally installed model name:

```bash
ollama list
export OLLAMA_MODEL='your-installed-model-name'
export OLLAMA_URL='http://localhost:11434'
python -m docguard extract data/documents/01_invoice.txt --backend ollama
python eval.py --backend ollama --report reports/ollama.json
```

`--model` and `--ollama-url` override the environment variables. `OLLAMA_MODEL` is required only for Ollama; `OLLAMA_URL` defaults to localhost. Choosing a remote URL sends the document there. Structured JSON uses Ollama's `/api/generate`, temperature 0, and non-streaming responses. Model quality, context capacity, latency, and truncation must be evaluated for the chosen model. No real-model accuracy or latency is reported in this submission.

## Project structure

```text
src/docguard/
  schema.py       Public result and internal evidence contracts
  providers.py    Mock, Ollama, and replay adapters
  normalize.py    Dates, numeric formats, RU/KZ word amounts
  parsing.py      Labelled source evidence and supported item layouts
  pipeline.py     Validation, grounding, safety scan, conflict rules
  cli.py          File/stdin interface and exit codes
  evaluation.py   Metrics and frozen-gold evaluation
data/             Manifest, 14 text inputs, 14 complete gold JSON files
tests/            Unit, pipeline, transport, CLI, and metric tests
docs/             Requirement mapping, verification, baseline report
REFLECTION.md     Tradeoffs, AI disclosure, and architecture answer
```

The external runtime dependency is Pydantic; tests use the Python standard library. Dependency versions are pinned. CI runs the same tests and evaluation on Python 3.11/3.12 when the repository is pushed to GitHub; this local delivery does not claim a completed hosted CI run.

## Scope, limitations, and next work

All mandatory Task A deliverables are implemented; [the requirements map](docs/REQUIREMENTS.md) points to the relevant files. Work is intentionally limited to a text CLI: no UI, PDF/OCR ingestion, database, queues, or paid model. The generalization tradeoff is deliberate: unknown layouts, unsupported word grammar, credits/negative amounts, wrapped item rows, and unlabeled organizations may be missed. BIN structure is checked, not legal validity. Binary JSON numbers are used for interchange after decimal parsing; this is not an accounting ledger.

Context remains limited to recognized role markers and line layouts: unfamiliar date-role wording can be missed, and buyer-section heuristics can miss a supplier in unusual layouts. The deterministic safety scan covers supported labels only. Schema validation and source references reduce invention but cannot prove that a document itself is truthful or that every cited value has the correct business role. Crafted text that resembles supported labels remains a limitation. Confidence is not a reliability estimate suitable for automatic payment approval.

With more time, prioritize a separately annotated, unseen dataset, a live-model comparison, better role/span evidence, and calibrated abstention thresholds; then extend normalization based on measured errors. There is no reason to add infrastructure before measuring those failure modes.

This implementation and documentation were created with AI assistance. Commit history records actual stages and uses an explicit Codex author; no candidate work history or human-only authorship is implied. Review the code and reflection before submitting and be prepared to explain and modify it. The archive includes `.git`; a public remote has not been created and no submission email has been sent.

## Technical references

- [Pydantic configuration](https://docs.pydantic.dev/latest/api/config/) for strict types, forbidden extra keys, and finite numbers.
- [Ollama generation API](https://docs.ollama.com/api/generate) for JSON Schema output and non-streaming requests.
