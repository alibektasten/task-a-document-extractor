# Task A requirement map

| Assignment requirement | Implementation / evidence |
| --- | --- |
| Text input to fixed-schema JSON | `python -m docguard extract`; `src/docguard/schema.py` |
| No invented missing BIN/date/VAT | Nullable fields; strict evidence parsers; no clock, registry lookup, or VAT arithmetic; `tests/test_pipeline.py` |
| Conflicting dates/totals in warnings | Deterministic audit plus selection in `pipeline.py`; README rules; cases 01/02/08 |
| Programmatic output validation | Strict Pydantic input/output models, finite nonnegative numbers, actual calendar dates, forbidden extra properties |
| Show behavior when model output is invalid | Replay command and `examples/invalid-response.json`; retry and fail-closed tests |
| API optional; real pipeline and eval | Deterministic mock is default; optional Ollama adapter; no gold lookup |
| Three supplied and at least seven authored examples | 3 supplied + 11 authored, all listed in `data/manifest.json` |
| At least three difficult authored examples | 9 authored cases explicitly tagged `hard` |
| Gold JSON for every document | Matching `data/gold/*.json`, validated before each evaluation |
| One-command mini-eval | `python eval.py` or `make eval` |
| Per-field accuracy | All top-level fields and nested item leaf fields; JSON report includes populated-value accuracy |
| Hallucinations and omissions counted separately | Dedicated counts, plus wrong values and collection errors; counter-injection tests |
| README from scratch, tests, completion/limitations | README includes complete install/run commands, variables, failure demo, scope and unverified environments |
| Reflection: five questions, 10–15 sentences | 12 sentences in the main reflection; explicit AI assistance disclosure |
| Architecture question: 5–10 sentences | 8 sentences in the architecture section; 300k docs/month and 0.50 KZT/doc budget |
| Meaningful commit history | Actual staged local commits in `.git`, included in the delivery ZIP |
| Submission format | [Public GitHub repository](https://github.com/alibektasten/task-a-document-extractor) and ZIP with `.git`; submission email is left to the applicant |

Task B, a user interface, and production infrastructure are intentionally outside scope.
