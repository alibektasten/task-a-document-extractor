# Corpus and annotation policy

The expected JSON files were authored from the text and documented policies, independently of executing the extractor. They are frozen regression expectations, not automatically regenerated predictions. Do not update gold merely to make a new implementation pass.

| ID | Source | Purpose |
| --- | --- | --- |
| 01_invoice | Supplied 1 | Table, explicit VAT, subtotal versus payable |
| 02_offer | Supplied 2 | Issue versus expiry; no inferred quantities or total |
| 03_kazakh_ocr | Supplied 3 | Bilingual supplier, damaged BIN, Kazakh words, tax exemption |
| 04_missing | Authored, hard | Missing supplier/date/amounts; item with unknown numbers |
| 05_russian_words | Authored, hard | Russian amount words, tiyn, leading-zero BIN, explicit zero VAT |
| 06_bilingual | Authored, hard | Kazakh month, mixed item name, rate-only VAT |
| 07_damaged | Authored, hard | OCR BIN and amount corruption; impossible calendar date |
| 08_conflicts | Authored, hard | Two issue dates and two equal-priority totals |
| 09_currency_conflict | Authored, hard | Explicit EUR and USD conflict |
| 10_buyer_bin | Authored, hard | Buyer's separate BIN must not become supplier BIN |
| 11_expiry_only | Authored, hard | Expiry is not issue date; no total arithmetic |
| 12_instructions_in_document | Authored, hard | Embedded instructions do not establish field evidence |
| 13_zero_decimal | Authored | Zero versus null, decimal comma, ISO date |
| 14_unknown | Authored | Unknown type and fully absent business fields |

Supplied texts were transcribed from the assignment PDF, preserving the visible wording, values, and OCR-damaged identifier; formatting-only spacing was normalized. Table columns retain at least two spaces because plain text has no cell metadata. The original PDF is not included in the repository.

Gold contains every public field, confidence, and expected warning strings. Business accuracy is reported separately from metadata exactness; heuristic confidence values in gold express the documented policy, not expert-calibrated certainty. The synthetic BINs in authored cases test 12-digit syntax only and are not asserted to identify real companies.

There is no independent test split: both the handwritten rules and this small corpus are visible during development. Passing it establishes reproducibility and regression coverage, not generalization. Additional tests generate previously unseen names and amounts, inject malformed responses, and intentionally corrupt predictions to check metric definitions.
