# hpvd-nrb — Manithy v1

**HPVD Knowledge Retrieval Engine | NRB Component | Deterministic Attestation**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.0.0-alpha2](https://img.shields.io/badge/version-1.0.0--alpha2-orange.svg)](#)
[![Tests: 147 passed](https://img.shields.io/badge/tests-147%20passed-brightgreen.svg)](#running-tests)

---

## Overview

HPVD is a **knowledge retrieval engine** that runs in the **NRB (Non-Binding Realm)** within the **Manithy v1 — Deterministic Attestation** system. The main role of HPVD is to retrieve relevant Policy, Product, Rule Mapping, and Document Schema from the Knowledge Layer based on `observed_data` produced by the Parser.

**Critical design principles:**
- **Non-binding:** HPVD output is *candidates* (informative, not authoritative). There is no decision-making here.
- **Sector-agnostic:** One engine for Banking, Finance, Chatbot, and other sectors.
- **Deterministic:** Same input -> same candidates, same order.
- **Traceable:** Each candidate includes `provenance` (data source).

HPVD consists of two layers:
- **Primary:** `KnowledgeRetrievalStrategy` — sector filter + field matching -> Policy/Product/RuleMapping candidates
- **Legacy:** `FinanceRetrievalStrategy` — analog search for OHLCV market data (still valid, not primary interface)

---

## Architecture

### Manithy v1 Pipeline (simplified)

```
[ INPUT: request + files ]
          │
          ▼
┌─────────────────────────────────────────────┐
│ NRB — Non-Binding Realm                     │
│                                             │
│  Parser (sector-specific)                   │
│  → observed_data + documents + metadata     │
│          │                                  │
│          ▼                                  │
│  HPVD  ◄─── Knowledge Layer                │
│  (sector filter + field match)              │
│  → candidates [{type, data, provenance}]   │
│          │                                  │
│          ▼                                  │
│  PMR  → hypotheses                          │
│          │                                  │
│          ▼                                  │
│  Knowledge Builder → KNOWN/UNKNOWN/CONFLICT │
└─────────────────────────────────────────────┘
          │
          ▼  Boundary t-1 (freeze observed state)
┌─────────────────────────────────────────────┐
│ RB CORE                                     │
│  VectorState → V1 (Coverage) → V3 (Decision)│
│  → Evidence Pack                            │
└─────────────────────────────────────────────┘
```

### Adapter Layer (HPVDPipelineEngine)

```
J13_PostCoreQuery (domain: "knowledge" | "finance" | "document")
  → J13Adapter (translate to strategy-specific query dict)
  → StrategyDispatcher (route by domain)
      ├── KnowledgeRetrievalStrategy → Policy/Product/RuleMapping candidates
      ├── FinanceRetrievalStrategy   → HPVDEngine (trajectory analog search)
      └── DocumentRetrievalStrategy → BM25/vector text search
  → J14_RetrievalRaw   (raw candidates)
  → J15_PhaseFilteredSet (filtered candidates)
  → J16_AnalogFamilyAssignment (grouped by type/family)
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
venv\Scripts\pytest.exe tests/ -q
# Expected: 147 passed, 9 skipped (live KL integration), ~43 warnings
```

### 3. Knowledge Retrieval (Primary — Manithy v1)

```python
from hpvd.adapters import HPVDPipelineEngine
from hpvd.adapters.strategies import KnowledgeRetrievalStrategy

# Knowledge corpus (Policy / Product / RuleMapping / DocumentSchema dicts)
corpus = [
    {
        "object_type": "policy",
        "policy_id": "POLICY_SME_LOAN_V1",
        "sector": "banking",
        "eligibility_rules": {"min_income": 3_000_000},
        "required_documents": ["loan_application_form", "identity_document"],
        "provenance": {"source": "bank_internal_policy"},
    },
    {
        "object_type": "rule_mapping",
        "mapping_id": "RULE_MAP_SME_LOAN_V1",
        "sector": "banking",
        "v1_required_fields": ["loan_amount", "beneficiary_name"],
        "v3_required_fields": ["loan_amount", "income", "dti_ratio"],
        "provenance": {"source": "core_binding_definition"},
    },
]

pipeline = HPVDPipelineEngine()
pipeline.register_strategy(KnowledgeRetrievalStrategy())
pipeline.build_knowledge_index(corpus)

result = pipeline.process_query({
    "query_id": "REQ_001",
    "scope": {"domain": "knowledge"},
    "observed_data": {"loan_amount": 50_000_000, "income": 10_000_000},
    "sector": "banking",
})

for candidate in result.j14.candidates:
    print(f"type={candidate['knowledge_type']}, id={candidate['data'].get('policy_id') or candidate['data'].get('mapping_id')}")
# type=policy, id=POLICY_SME_LOAN_V1
# type=rule_mapping, id=RULE_MAP_SME_LOAN_V1
```

### 4. Finance Market Data (Legacy — FinanceRetrievalStrategy)

```python
from hpvd import HPVDEngine, HPVDInputBundle, HPVD_Output

engine = HPVDEngine()
engine.build_from_bundles(list_of_bundles)
output: HPVD_Output = engine.search_families(query_bundle)
d = output.to_dict()
```

---

## Running Tests

```powershell
venv\Scripts\pytest.exe tests/ -v                                      # verbose
venv\Scripts\pytest.exe tests/ -q                                      # quick summary
venv\Scripts\pytest.exe tests/ --cov=src/hpvd --cov-report=html       # coverage
venv\Scripts\pytest.exe tests/test_knowledge_retrieval.py -v           # knowledge tests only
```

---

## Knowledge Output Schema (J14 — knowledge domain)

```json
{
  "schema_id": "manithy.hpvd_retrieval_raw.v1",
  "query_id": "REQ_001",
  "domain": "knowledge",
  "candidates": [
    {
      "knowledge_type": "policy",
      "sector": "banking",
      "data": {
        "policy_id": "POLICY_SME_LOAN_V1",
        "required_documents": ["loan_application_form", "identity_document"],
        "eligibility_rules": {"min_income": 3000000}
      },
      "provenance": {"source": "bank_internal_policy", "created_at": "2026-01-01"}
    },
    {
      "knowledge_type": "rule_mapping",
      "sector": "banking",
      "data": {
        "mapping_id": "RULE_MAP_SME_LOAN_V1",
        "v1_required_fields": ["loan_amount", "beneficiary_name"]
      },
      "provenance": {"source": "core_binding_definition"}
    }
  ],
  "diagnostics": {
    "sector_matched": "banking",
    "objects_returned": 2,
    "rule_mapping_forced": true
  }
}
```

---

## Project Structure

```
hpvd-nrb/
├── src/hpvd/                           # Core library
│   ├── engine.py                       # HPVDEngine (finance market data)
│   ├── trajectory.py                   # HPVDInputBundle (finance)
│   ├── sparse_index.py                 # Regime inverted index (finance)
│   ├── dense_index.py                  # FAISS wrapper
│   ├── family.py                       # Family formation engine
│   └── adapters/                       # Multi-domain adapter layer
│       ├── knowledge_schemas.py        # PolicyObject, ProductObject, etc.
│       ├── j_file_schemas.py           # J13/J14/J15/J16 typed schemas
│       ├── pipeline_engine.py          # HPVDPipelineEngine (J13→J16)
│       ├── strategy_dispatcher.py      # Domain → strategy routing
│       └── strategies/
│           ├── knowledge_strategy.py   # KnowledgeRetrievalStrategy (NEW)
│           ├── finance_strategy.py     # FinanceRetrievalStrategy
│           └── document_strategy.py    # DocumentRetrievalStrategy
├── tests/                              # 147 automated tests
│   ├── test_knowledge_retrieval.py     # K1–K7 + schema tests (NEW)
│   └── ...                            # 72 existing tests
├── docs/
│   ├── HPVD_CORE.md                   # Technical reference (Manithy v1)
│   ├── MANITHY_INTEGRATION.md         # Pipeline + J-files + NRB integration
│   └── CHANGELOG.md                   # Status + roadmap
└── requirements.txt
```

---

## MVP Status (Manithy v1 Architecture)

| Capability | Status |
|-----------|--------|
| KnowledgeRetrievalStrategy (sector filter + field match) | ✅ |
| Mandatory rule_mapping retrieval | ✅ |
| Provenance on all candidates | ✅ |
| Sector-agnostic (Banking/Finance/Chatbot) | ✅ |
| Multi-domain adapter (J13→J14→J15→J16) | ✅ |
| HPVDPipelineEngine.build_knowledge_index() | ✅ |
| Knowledge schemas (Policy/Product/RuleMapping/DocumentSchema) | ✅ |
| Finance market data (FinanceRetrievalStrategy — legacy) | ✅ |
| Document full-text (DocumentRetrievalStrategy) | ✅ |
| KL REST integration | ✅ |
| 147 automated tests (72 legacy + 13 knowledge + rest) | ✅ |

**Not yet implemented:** NRBOrchestrator, Parser layer, PMR, Knowledge Builder, REST API. See [CHANGELOG.md](docs/CHANGELOG.md).

---

## Documentation

| File | Contents |
|------|-----|
| [docs/HPVD_CORE.md](docs/HPVD_CORE.md) | Technical reference: knowledge schemas, retrieval pipeline, input/output contract, API |
| [docs/MANITHY_INTEGRATION.md](docs/MANITHY_INTEGRATION.md) | Manithy v1 pipeline, HPVD in NRB, J-files reference, VectorState (Core), KL integration |
| [docs/CHANGELOG.md](docs/CHANGELOG.md) | Architecture pivot notes, MVP deliverables, roadmap |

---

## Dependencies

```
numpy>=1.26.0       faiss-cpu>=1.7.4
scipy>=1.13.0       rank-bm25>=0.2.2
scikit-learn>=1.4.0 pytest>=7.0.0 (dev)
```

Full pinned deps: `requirements.txt` | Editable install: `pip install -e ".[dev]"`

---

## License

MIT License — Project: Manithy v1 / hpvd-nrb
