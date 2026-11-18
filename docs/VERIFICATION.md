# Verification record

Verified locally on **18 November 2026**, on macOS arm64 with Python **3.12.14**, Pydantic **2.12.5**, and pydantic-core **2.41.5**.

| Check | Observed result |
| --- | --- |
| Fresh folder, new virtual environment, pinned requirements, editable package installation | Passed |
| `python -m pip check` | No broken requirements |
| `python -m unittest discover -s tests -v` | 50 tests passed |
| `python eval.py` | 14 documents, every top-level field exact, no pipeline failures |
| Hallucinations / omissions | 0 / 0 on the curated mock baseline |
| Exact business documents | 14 / 14 |
| Extra / missing line items | 0 / 0 |
| `make check` in the fresh folder | Passed |
| File input versus stdin, UTF-8 BOM | Matching valid output |
| Missing file, invalid UTF-8, input limit | Valid failure JSON and exit 2 |
| Invalid response replay | Retry, valid abstaining JSON, exit 2 |
| Corrupt gold data | Evaluation stops with exit 2 |
| Deliberately inserted hallucination/omission | Evaluator reports distinct counters, including nested fields |
| Ollama adapter | Request, envelope, timeout, connection failure, response size tested with mocked transport |

The fresh-folder run used a separate source copy without `.git`, existing virtual environments, package metadata, or bytecode. It ran the README's environment creation, dependency installation, editable install, dependency check, invoice demo, tests, evaluation, and Makefile checks.

The host's Python HTTPS client could not validate the package-server certificate chain. To complete the clean installation without disabling TLS verification, the exact pinned wheels were downloaded using macOS's working HTTPS client and checked against the SHA-256 digests in PyPI's HTTPS metadata. `PIP_NO_INDEX=1` and `PIP_FIND_LINKS` pointed pip at that local wheel cache during verification; the application and README commands were otherwise unchanged. The wheel cache is not part of the deliverable, and ordinary installations use PyPI normally.

The full machine-readable result is [evaluation-baseline.json](evaluation-baseline.json). Regenerate it with:

```bash
python eval.py --report docs/evaluation-baseline.json
```

**Not verified:** live Ollama model quality or latency, hosted GitHub CI, Windows, Linux, Python 3.11 locally, or production throughput. CI configuration covers Python 3.11 and 3.12 on Linux when subsequently run. No benchmark result here should be presented as real-model performance or unseen-document accuracy.
