# Reflection

Implementation notes prepared with AI assistance; review and adapt only where needed to reflect your own understanding before submission.

## 1. What was hardest, and why?

The hardest part was distinguishing a fact present in the document from a plausible value with the wrong business role, such as an expiry date or a buyer's BIN.
Restricting the provider to source-line references makes unsupported invention harder, but role checks and conservative normalization still have to happen in code.

## 2. What compromise was made for the four-hour scope?

The implementation uses a deterministic mock by default and bounded text formats instead of requiring paid inference, OCR, or a large document-processing stack.
This makes the pipeline reproducible and explainable, while knowingly sacrificing recall on unseen layouts and withholding any claim of real-model quality.

## 3. What would be the first priority with eight more hours?

The first priority would be a separately annotated, unseen set with realistic OCR and business-role ambiguity, followed by an actual Ollama run against the same frozen evaluator.
The next changes would follow measured error costs, especially unsupported populated fields, rather than simply adding more regexes until the visible examples pass.

## 4. Where was AI used, and what needed correction?

AI assistance was used for requirements analysis, implementation, corpus drafting, tests, and documentation, so this is an AI-assisted submission rather than a claim of unaided authorship.
The initial dependency pins were corrected to a verified compatible release set, and a currency-detection path was tightened so unrelated text columns would not establish currency evidence.
Expected JSON was authored separately from extraction output, and tests deliberately introduced wrong predictions to check that the evaluator could detect them.
The applicant should review the code and these notes before the interview, because generated implementation notes cannot establish personal understanding.

## 5. Which requirement was ambiguous, and how was it interpreted?

The assignment does not specify whether total amount means subtotal or final payable amount, whether an expiry date counts as a conflicting date, or whether tax exemption means numeric zero.
The documented choices are to prefer an explicit final payable amount, warn about distinct recognized dates while selecting an issue date, and leave VAT null unless a numeric amount is stated.

## Architecture: 10,000 documents/day, 150,000 KZT/month

Assuming 30 processing days, 10,000 documents per day means about 300,000 per month, leaving an average inference budget of 0.50 KZT per document.
That arithmetic is a budget ceiling, not evidence that any particular model, hardware rental, or token price fits it.
I would measure input/output tokens, retry rates, latency, and cost per accepted document on representative data before selecting a model or claiming capacity.
Known templates would use deterministic extraction, while only uncertain cases would receive a bounded model call and a limited retry allowance.
Content-hash deduplication scoped to each customer, together with model and parser versioning, would avoid paying again for identical documents without leaking results across tenants.
A small worker queue would handle bursts, with bounded concurrency, idempotent jobs, explicit failure states, and metrics separating hallucinations, omissions, and human-review load.
I would abandon unconditional large-model calls, multi-agent inference chains, and repeated self-correction loops, then compare measured API cost against the fully accounted cost of local inference.
If the target quality cannot be achieved inside the budget, the system should abstain and expose a review backlog rather than fill missing values, while review staffing and OCR costs must be budgeted separately from inference.
