# Lead Triage Agent — Single Grain AI Automation Intern 012

**Brief version:** `2026-07`  
**Implementation:** Python 3.10+ · Ollama · Qwen2.5 7B  
**Fixture SHA-256 (observed):** `cc1927ca771c37b186a2abdb7b9757594da79ec6dda074e5a514dd2761cc8599`

A reproducible, auditable lead-triage agent that processes the challenge CSV and emits one decision per lead: `QUALIFY`, `NURTURE`, `REJECT`, or `ESCALATE`. It uses deterministic validation and verification, plus optional local LLM review for eligible cases. No paid OpenAI API key is necessary.

## Repository layout

```text
lead-triage-agent/
├── main.py                       # CLI, business rules, Ollama review, audit logging
├── verification.py               # Verification and routing checks
├── requirements.txt               # Python dependency for local Ollama API client
├── README.md
├── submission.md                  # Written challenge response (max four pages)
├── fixtures/
│   └── inbound_leads.csv         # Original fixture; do not edit
├── outputs/
│   ├── decisions.csv             # Final full-fixture decisions
│   ├── run.jsonl                 # Matching run audit log
│   └── verification.jsonl        # Verification evidence for matching run
├── evidence/
│   └── test_results.txt          # Captured unit test output
└── tests/
    └── test_agent.py
```

## Prerequisites

- Python **3.10 or newer**, `pip`, and a virtual environment.
- For **AI-assisted mode**: [Ollama](https://ollama.com/) installed locally and the `qwen2.5:7b` model downloaded. Ensure adequate disk space and RAM for this local model.
- No external database or API account is required for this fixture demo.

## Setup (Ubuntu / Linux)

From the directory containing `main.py`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install Ollama using instructions from its official site, start the service if needed, and download the model:

```bash
ollama pull qwen2.5:7b
ollama list
curl -s http://localhost:11434/api/tags
```

On a typical Ubuntu installation Ollama runs as a service; use `ollama serve` **only if** the server is not already running. Do not start a second instance on the same port.

## Run the agent

### Option A — AI-assisted classification (recommended for evaluation)

```bash
source .venv/bin/activate
export OPENAI_MODEL="qwen2.5:7b"
# Optional: default is http://localhost:11434/v1
export OLLAMA_BASE_URL="http://localhost:11434/v1"

python main.py \
  --mode openai \
  --input fixtures/inbound_leads.csv \
  --output outputs/decisions.csv \
  --log outputs/run.jsonl
```

**Note:** The CLI argument is named `--mode openai` for backward compatibility. In the supplied `main.py`, this mode sends requests to **local Ollama**, using the OpenAI-compatible protocol. It does **not** call OpenAI's paid servers. The model may take time to load for its first request.

### Option B — Offline deterministic baseline

```bash
python main.py \
  --mode rules \
  --input fixtures/inbound_leads.csv \
  --output outputs/decisions_rules.csv \
  --log outputs/run_rules.jsonl
```

The baseline does not require Ollama to be running. **Caution:** Both runs write `verification.jsonl` in the output CSV's parent directory; use a separate output directory if retaining evidence from both modes.

### Output files

- `outputs/decisions.csv` — CSV with exactly `lead_id,decision,reason,confidence`.
- `outputs/run.jsonl` — one JSON event per line: start metadata, each lead's decision, model-review status, and completion metadata.
- `outputs/verification.jsonl` — verification decisions and human-review routing for each lead, generated alongside the decisions file.

The run log records the input CSV SHA-256 and final decision CSV SHA-256. These logs are overwritten when rerunning with the same paths, so archive evidence you want to keep before running again.

## What happens on each lead

1. **Ingest** the fixture and compute its SHA-256 checksum.
2. **Validate** timestamps, contact information, website format, budget, and message content.
3. **Apply deterministic policy** for sensitive cases: privacy requests, suspicious executable links, prompt-injection attempts, junk submissions, duplicates, and other identified exceptions.
4. **Verify** the provisional result through `verification.py`, deciding whether manual review or more information is required.
5. **Review with Qwen2.5 7B** *when eligible and AI mode is enabled*. Model input is untrusted lead data, not executable instructions. The model must return structured JSON.
6. **Enforce safeguards** to avoid inappropriate qualification or overrides of protected decisions; errors fail to human escalation rather than being silently accepted.
7. **Write outputs and evidence** to CSV and JSONL.

The monthly budget cutoff of **USD 5,000 is an assumed demonstration rule**, **not** a published Single Grain qualification policy. Model confidence is a heuristic/self-reported value, **not a calibrated probability**. The agent does not browse or independently verify lead-supplied sites or identities.

## How to verify the run

Check the exact fixture fingerprint:

```bash
sha256sum fixtures/inbound_leads.csv
```

Expected for the supplied fixture used in testing:

```text
cc1927ca771c37b186a2abdb7b9757594da79ec6dda074e5a514dd2761cc8599
```

Verify there are 20 unique output leads:

```bash
python - <<'PY'
import csv
from collections import Counter
from pathlib import Path

with Path('outputs/decisions.csv').open(newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    assert reader.fieldnames == ['lead_id', 'decision', 'reason', 'confidence']
    rows = list(reader)

assert len(rows) == 20, f'Expected 20 leads, got {len(rows)}'
assert len({r['lead_id'] for r in rows}) == 20, 'Duplicate lead IDs'
assert all(r['decision'] in {'QUALIFY', 'NURTURE', 'REJECT', 'ESCALATE'} for r in rows)
print('PASS: 20 unique leads')
print('Decisions:', dict(Counter(r['decision'] for r in rows)))
PY
```

Distinguish **model-reviewed** rows from rule-only or skipped rows:

```bash
# See successful model reviews (expect at least one for an AI-assisted run)
grep '"status": "reviewed"' outputs/run.jsonl

# Check model failures and per-lead processing errors
grep -E '"status": "error"|"event": "lead_error"' outputs/run.jsonl
```

If `reviewed` never appears, **do not claim that the final run used live inference**: check the run's mode, local service status, and logs. A successful CSV alone proves completion, not AI participation.

## Tests

```bash
mkdir -p evidence
python -m py_compile main.py verification.py
python -m unittest discover -s tests -v 2>&1 | tee evidence/test_results.txt
```

**Observed testing evidence:** 12 unit tests passed on the supplied fixture; tests exercise the deterministic/verification workflow, **not a live model inference benchmark**. The fixture run produced **3 QUALIFY, 8 NURTURE, 3 REJECT, and 6 ESCALATE**; counts alone do not establish prediction accuracy. Check the current files and logs before reporting the results as your final run.

## Real failure detected and corrected

An earlier model-assisted run incorrectly returned `QUALIFY` for **L-010**, a junk/test submission with an inflated budget. Inspection identified overreliance on the budget field. Deterministic junk classification was protected from AI promotion; a later run returned `REJECT`. Keep genuine before/after output and matching logs as evidence; don't reconstruct execution evidence.

## Human review and limitations

Human judgment is required for privacy/data-deletion requests, suspicious executable links, unresolved identity issues, compliance-sensitive work, and other matters requiring authorization or sufficient evidence. NURTURE for a compliance-sensitive lead **does not** authorize launching a campaign.

This is a local, fixture-driven prototype. Production deployment would need persistent cross-run deduplication, a CRM or ticketing integration, retries and idempotency, privacy/access controls on logs, monitored model quality, and human-labeled evaluation data. No endpoint or external claim is independently checked by the agent.

## Submission

The submission packet should include `submission.md` (brief `2026-07`, fixture checksum, architecture, challenges, actual failure correction, human decisions, scale risks, evidence tiers, AI disclosure, personal automation answer) together with the **working source**, **full decisions CSV**, **matching run log**, and **verification log**. Keep written material at or under four rendered pages; supporting code and logs do not count toward this limit.
