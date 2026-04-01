# HPVD-M22

**Hybrid Probabilistic Vector Database for Trajectory Intelligence**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.0.0-alpha1](https://img.shields.io/badge/version-1.0.0--alpha1-orange.svg)](#)
[![Tests: 72 passed](https://img.shields.io/badge/tests-72%20passed-brightgreen.svg)](#running-tests)

---

## Overview

HPVD adalah **multi-domain retrieval engine** untuk mencari analog historis yang secara struktur mirip dengan query (trajectory finansial *atau* text chunk), lalu mengelompokkannya menjadi **Analog Families** — cluster koheren dengan explicit uncertainty markers.

**Critical design principle:** HPVD adalah **outcome-blind**. Ia menghasilkan structured empirical evidence, tidak menghitung probabilitas atau membuat prediksi. Itu tanggung jawab downstream systems (PMR-DB).

HPVD terdiri dari dua layer:
- **Core engine** — domain-agnostic sparse + dense retrieval dengan family formation (`HPVDEngine`)
- **Adapter layer** — domain-specific strategy pattern yang mentranslasi J-file envelopes ke core queries dan emit structured J-file outputs (`HPVDPipelineEngine`)

---

## Core Architecture

### Core Engine (domain-agnostic)

```
Query (HPVDInputBundle: 60×45 trajectory + 16-d DNA)
  → Validate (HPVDInputBundle.validate())
  → Sparse Filter (SparseRegimeIndex — O(1) inverted index by regime)
  → Dense Search (FAISS IVFFlat/Flat — 256-d PCA embeddings)
  → Multi-Channel Fusion (trajectory dist × 0.7 + DNA dist × 0.3)
  → Family Formation (group by regime, compute coherence)
  → HPVD_Output (analog_families + retrieval_diagnostics + metadata)
```

### Adapter Layer (multi-domain pipeline)

```
J13_PostCoreQuery (domain: finance | document | banking | …)
  → J13Adapter (translate to domain-specific query dict)
  → StrategyDispatcher (route to matching RetrievalStrategy)
      ├── FinanceRetrievalStrategy   → HPVDEngine (trajectory search)
      └── DocumentRetrievalStrategy → BM25/vector text search
  → J14_RetrievalRaw   (raw candidate list)
  → J15_PhaseFilteredSet (phase-filtered candidates)
  → J16_AnalogFamilyAssignment (final family assignments)
```

---

## Quick Start

### 1. Setup

```powershell
python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
# atau: pip install -e ".[dev]"
```

### 2. Verify

```powershell
pytest tests/ -q
# Expected: 72 passed, ~32 warnings
```

### 3. Run Demo

```powershell
python -m src.demo_hpvd
```

---

## Running Tests

```powershell
pytest tests/ -v                                      # verbose
pytest tests/ -q                                      # quick summary
pytest tests/ --cov=src/hpvd --cov-report=html       # with coverage
pytest tests/test_contract.py -v                      # specific file
```

---

## Output Schema (`hpvd_output_v1`)

```json
{
  "metadata": {
    "hpvd_version": "v1",
    "query_id": "query_001",
    "schema_version": "hpvd_output_v1",
    "timestamp": "2024-01-15T00:00:00+00:00"
  },
  "retrieval_diagnostics": {
    "candidates_considered": 200,
    "candidates_admitted": 45,
    "families_formed": 3,
    "latency_ms": 12.5
  },
  "analog_families": [
    {
      "family_id": "AF_001",
      "members": [{"trajectory_id": "hist_034", "confidence": 0.57}],
      "coherence": {"mean_confidence": 0.55, "dispersion": 0.03, "size": 15},
      "structural_signature": {"phase": "stable_expansion", "avg_K": 5.2, "avg_LTV": 0.3},
      "uncertainty_flags": {"phase_boundary": false, "weak_support": false}
    }
  ]
}
```

**Programmatic serialization:**

```python
output = engine.search_families(query_bundle)
d = output.to_dict()                             # → dict
j = output.to_json(indent=2)                     # → JSON string
restored = HPVD_Output.from_dict(d)              # → HPVD_Output
```

---

## Project Structure

```
HPVD-M22/
├── src/hpvd/                  # Core library
│   ├── engine.py              # HPVDEngine + HPVD_Output
│   ├── trajectory.py          # Trajectory + HPVDInputBundle
│   ├── sparse_index.py        # Regime inverted index
│   ├── dense_index.py         # FAISS wrapper
│   ├── distance.py            # Hybrid distance calculator
│   ├── embedding.py           # PCA embedding computer
│   ├── dna_similarity.py      # Cognitive DNA matching
│   ├── family.py              # Family formation engine
│   ├── cli.py                 # CLI (build-index / search)
│   └── adapters/              # Multi-domain adapter layer
│       ├── j_file_schemas.py  # J13/J14/J15/J16 typed schemas
│       ├── pipeline_engine.py # HPVDPipelineEngine (J13→J16)
│       ├── strategy_dispatcher.py
│       └── strategies/        # FinanceStrategy, DocumentStrategy
├── tests/                     # 72 automated tests
├── docs/                      # Documentation
├── hpvd_outputs/              # Example output files
├── synthetic_data/            # Pre-generated test data
├── pyproject.toml
└── requirements.txt
```

---

## MVP Status

| Capability | Status |
|-----------|--------|
| Sparse + Dense retrieval | ✅ |
| Multi-channel fusion | ✅ |
| Analog Family formation | ✅ |
| Outcome-blind contract | ✅ |
| Serializer `hpvd_output_v1` | ✅ |
| CLI entrypoint | ✅ |
| Multi-domain adapter (J13→J16) | ✅ |
| KL integration (v2) | ✅ |
| 72 automated tests | ✅ |

**Not yet implemented:** Qdrant, REST API, PMR-DB, real market data. See [CHANGELOG.md](docs/CHANGELOG.md).

---

## Documentation

| File | Isi |
|------|-----|
| [docs/HPVD_CORE.md](docs/HPVD_CORE.md) | Technical reference: data model, distance formulas, search pipeline, quality gates, config, API |
| [docs/MANITHY_INTEGRATION.md](docs/MANITHY_INTEGRATION.md) | Manithy pipeline (18 stages), J-files reference, VectorState format, KL integration |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | MVP deliverables, roadmap (Phase 1–5), test history |

**Interactive demos (notebooks):**
- `HPVD_M22_Function_Walkthrough.ipynb` — walkthrough semua komponen core
- `HPVD_KL_Integration_Demo_klv2.ipynb` — KL v2 integration demo
- `HPVD_Test_Results_Visualization.ipynb` — visual explanation test scenarios

---

## HPVD → PMR-DB Boundary

```
HPVD (retrieval, structural)      PMR-DB (probabilistic, decisional)
────────────────────────          ──────────────────────────────────
analog_families[]                  Probability computation
  ├── members + confidence          Confidence intervals
  ├── coherence metrics             Entropy / abstention decisions
  └── uncertainty_flags             Calibrated forecasts
retrieval_diagnostics
metadata (schema: hpvd_output_v1)
```

**Key rule:** HPVD computes structural similarity. PMR-DB computes probabilities. Boundary: `hpvd_output_v1` JSON.

---

## Dependencies

```
numpy>=1.26.0       faiss-cpu>=1.7.4
pandas>=2.1.0       rank-bm25>=0.2.2
scipy>=1.13.0       pytest>=7.0.0 (dev)
scikit-learn>=1.4.0
```

Full pinned deps: `requirements.txt` | Editable install: `pip install -e ".[dev]"`

---

## License

MIT License — Project: Kalibry Finance / Matrix22
