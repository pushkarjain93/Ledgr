# ReconAI — file map

Razorpay Buildathon, Track 04 (AI Finance Controller), direction:
multi-source reconciliation. Stack: Python + Pandas + Streamlit + Claude/Gemini.

## Core pipeline (run in this order)

| File | Role |
|---|---|
| `config.py` | Tolerance bands, COD ageing windows, reason legend, priority banding, paise helpers. Single source of truth for every threshold. |
| `gen_data.py` | Synthetic data generator. Stratified anomaly injection. `RECONAI_SEED` env var controls the seed. |
| `validate_data.py` | Asserts the generated labels agree with `config.py`. Run after any config change. |
| `engine.py` | The 5-tier waterfall (plus Tier 0 COD pre-check). Reads CSVs, writes `data/run_results.csv`, prints the scorecard. Exits non-zero on misclassification. |

```bash
python3 gen_data.py && python3 validate_data.py && python3 engine.py
```

## Data

| File | Contents |
|---|---|
| `data/orders.csv` | 259 internal order records |
| `data/settlements.csv` | 231 bank + gateway rows |
| `data/ground_truth.csv` | 265 labelled expected outcomes |
| `data/run_results.csv` | Engine output: tier, status, reason, delta, amount at risk, priority |

## UI

| File | Status |
|---|---|
| `demo.html` | Interactive prototype. Self-contained, real engine output baked in. Not runtime-connected. |
| `build_demo.py` | Generates `demo.html` from `run_results.csv`. |
| `app.py` | **NOT BUILT YET** — the Streamlit deliverable. |

## Design reference (not code)

`FEATURES.md`, `dashboard_mockup.svg`, `login_mockup.svg`, `mockup.py`,
`login_mockup.py`, `index.html`

## Architecture

Tier 0  COD timing pre-check   COD, no remittance yet -> age it (0-7 / 8-14 / 15+)
Tier 1  Exact match            gateway_ref_id + amount identical
Tier 2  Known deduction        ref matches, shortfall inside the fee band
Tier 3  Variance               ref matches, amount does not -> AI diagnostic
Tier 4  UTR fallback           no ref (COD / direct transfer), match on bank_utr
Tier 5  Unmatched              never guess; exception with a stated reason

Reason codes: R1 awaiting remittance, R2 remittance overdue,
R3 unmatched/ambiguous, R4 partial payment, R5 large variance flagged by AI.

Two invariants: money is integer paise everywhere (no floats); the model never
produces a number, only a category plus one sentence.

## Current state

Data generator, validator and engine are complete and passing. Engine scores
100% on tier / disposition / reason with 0 false clears, holding across
multiple random seeds. 90.6% of records resolve with no AI call.
Streamlit `app.py` is the remaining piece.
