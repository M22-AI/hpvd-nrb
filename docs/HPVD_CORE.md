# HPVD Core — Technical Reference

> **HPVD (Hybrid Probabilistic Vector Database)** is a domain-agnostic knowledge retrieval engine that retrieves Policy, Product, Rule Mapping, and Document Schema based on `observed_data` from the Parser. HPVD operates in the **NRB (Non-Binding Realm)** — before Core, after the Parser. All outputs are *candidates-only* (non-authoritative); PMR and Knowledge Builder perform further processing.

**Version:** 1.0.0-alpha2 | **Project:** Manithy v1 — Deterministic Attestation System

---

## Table of Contents

1. [System Context](#1-system-context)
2. [Data Model — Knowledge Objects](#2-data-model--knowledge-objects)
3. [Retrieval Architecture](#3-retrieval-architecture)
4. [Input & Output Contract](#4-input--output-contract)
5. [Retrieval Pipeline](#5-retrieval-pipeline)
6. [Quality Gates & Test Scenarios](#6-quality-gates--test-scenarios)
7. [Configuration Reference](#7-configuration-reference)
8. [API Reference](#8-api-reference)
9. [FinanceRetrievalStrategy Internals](#9-financeretrievalstrategy-internals)

---

## 1. System Context

```
[ INPUT ]
    │  request + files
    ▼
┌─────────────────────────────────────────────┐
│ NRB — Non-Binding Realm                     │
│                                             │
│  Parser (sector-specific)                   │
│  → observed_data + documents + metadata     │
│       │                                     │
│       ▼                                     │
│  HPVD  ◄── Knowledge Layer                 │
│  (sector filter + field match)              │
│  → candidates [{type, data, provenance}]    │
│       │                                     │
│       ▼                                     │
│  PMR  → hypotheses                          │
│       │                                     │
│       ▼                                     │
│  Knowledge Builder                          │
│  → epistemic state (KNOWN/UNKNOWN/CONFLICT) │
└─────────────────────────────────────────────┘
    │
    ▼  Boundary t-1  (freeze observed state)
┌─────────────────────────────────────────────┐
│ RB CORE                                     │
│  Adapter → VectorState → V1 → V3 → Decision│
│  Evidence Pack                              │
└─────────────────────────────────────────────┘
```

**Key specifications:**

| Parameter | MVP Target | Production Target |
|-----------|-----------|-------------------|
| Supported sectors | Banking, Finance, Chatbot | Unlimited |
| Knowledge object types | 4 (Policy, Product, RuleMapping, DocumentSchema) | Extensible |
| Query latency | < 50ms | < 20ms |
| Determinism | Required (same input → same candidates) | Same |
| Traceability | Mandatory `provenance` per candidate | Same |

---

## 2. Data Model — Knowledge Objects

HPVD manages and retrieves four types of knowledge objects. All are stored as JSON and identified with a `sector` tag for filtering.

### 2.1 Policy

Eligibility and compliance rules that apply to a sector/product.

```json
{
  "policy_id": "POLICY_SME_LOAN_V1",
  "version": "1.0",
  "sector": "banking",
  "product_type": "sme_loan",
  "eligibility_rules": {
    "min_age": 21,
    "max_age": 60,
    "min_income": 3000000,
    "max_dti_ratio": 0.4,
    "min_business_age_months": 12
  },
  "compliance_rules": {
    "must_have_npwp": true,
    "must_not_blacklisted": true,
    "must_not_bankrupt": true
  },
  "required_documents": [
    "loan_application_form",
    "identity_document",
    "bank_statement",
    "financial_statement"
  ],
  "provenance": {
    "source": "bank_internal_policy",
    "created_at": "2026-01-01"
  }
}
```

### 2.2 Product

Information on limits, tenor, interest, and financial rules for a product.

```json
{
  "product_id": "SME_LOAN_STANDARD",
  "sector": "banking",
  "loan_constraints": {
    "min_amount": 5000000,
    "max_amount": 500000000,
    "tenor_options": [12, 24, 36, 60],
    "interest_type": "fixed"
  },
  "financial_rules": {
    "max_installment_to_income_ratio": 0.4,
    "late_penalty_rate": 0.02
  },
  "provenance": {
    "source": "product_catalog"
  }
}
```

### 2.3 Rule Mapping

Mapper between fields in the observed state and the requirements in V1 (Coverage) and V3 (Decision) in the Core layer.

```json
{
  "mapping_id": "RULE_MAP_SME_LOAN_V1",
  "sector": "banking",
  "v1_required_fields": [
    "loan_amount",
    "loan_contract_date",
    "beneficiary_name",
    "beneficiary_tax_code",
    "doc_application_present",
    "doc_financing_contract_present"
  ],
  "v3_required_fields": [
    "loan_amount",
    "income",
    "dti_ratio",
    "guarantee_amount",
    "claim_amount"
  ],
  "document_requirements": {
    "loan_application_form": "doc_application_present",
    "financial_statement": "doc_financial_statement_present",
    "bank_statement": "doc_bank_statement_present"
  },
  "consistency_rules": [
    {"rule": "claim_amount <= guarantee_amount"},
    {"rule": "loan_amount <= max_amount_product"}
  ],
  "provenance": {
    "source": "core_binding_definition"
  }
}
```

### 2.4 Document Schema

Expected field structure for a document type. Used by the Parser and HPVD to validate availability.

```json
{
  "doc_type": "loan_application_form",
  "sector": "banking",
  "fields": ["applicant_name", "applicant_age", "income", "loan_amount", "tenor"],
  "required": ["applicant_name", "income", "loan_amount"],
  "provenance": {
    "source": "bank_form_template"
  }
}
```

### 2.5 Policy Feature Index (Optional)

Additional index to speed up field-based matching — maps field names to relevant knowledge objects.

```json
{
  "index_id": "POLICY_FEATURE_INDEX",
  "sector": "banking",
  "features": {
    "income": ["policy_sme_loan_v1"],
    "loan_amount": ["product_sme_loan_standard"],
    "documents": ["policy_sme_loan_v1"]
  }
}
```

---

## 3. Retrieval Architecture

### 3.1 KnowledgeIndex

`KnowledgeIndex` is an in-memory store that keeps all knowledge objects, organized per sector. It supports O(1) lookup by sector, and field matching O(F) where F = number of fields in `observed_data`.

| Operation | Complexity | Description |
|-----------|-----------|------------|
| `add()` | O(1) | Insert into sector bucket |
| `filter_by_sector()` | O(1) | Direct bucket lookup |
| `match_by_fields()` | O(F × K) | F = observed fields, K = candidates per type |
| `get_rule_mapping()` | O(1) | Mandatory — always retrieved |

**Memory:** Proportional to the size of the knowledge corpus. Typical starter: < 1 MB.

### 3.2 Retrieval Strategy: KnowledgeRetrievalStrategy

`KnowledgeRetrievalStrategy` implements the `RetrievalStrategy` ABC with domain `"knowledge"`.

| Step | Name | Description |
|------|------|------------|
| 1 | Sector Filter | Take all knowledge objects with `sector` == `metadata.sector` |
| 2 | Field-Based Matching | Match fields in `observed_data` with `eligibility_rules` / `loan_constraints` |
| 3 | Mandatory Retrieval | Always include `rule_mapping` that matches the sector |
| 4 | Format Output | Wrap each object into `KnowledgeCandidate({type, data, provenance})` |

### 3.3 Strategy Dispatcher

`StrategyDispatcher` routes queries based on `scope.domain` from J13. For knowledge retrieval, `domain = "knowledge"`. Finance market data remains available via `domain = "finance"` (see Section 9).

---

## 4. Input & Output Contract

### 4.1 Input (from Parser via NRB Orchestrator)

```json
{
  "observed_data": {
    "applicant_name": "Budi Santoso",
    "loan_amount": 50000000,
    "income": 10000000,
    "nik": "1234567890123456"
  },
  "documents": [
    {"doc_type": "loan_application_form", "present": true},
    {"doc_type": "bank_statement", "present": true},
    {"doc_type": "financial_statement", "present": false}
  ],
  "metadata": {
    "sector": "banking",
    "parser_version": "parser_banking_v1"
  }
}
```

**In the pipeline adapter (HPVDPipelineEngine)**, the input is packaged as J13:
```json
{
  "query_id": "REQ_LOAN_0001",
  "scope": {"domain": "knowledge"},
  "observed_data": {"applicant_name": "Budi Santoso", "loan_amount": 50000000},
  "sector": "banking"
}
```

### 4.2 Output (to PMR)

```json
{
  "candidates": [
    {
      "type": "policy",
      "data": {
        "policy_id": "POLICY_SME_LOAN_V1",
        "required_documents": ["loan_application_form", "identity_document", "bank_statement", "financial_statement"],
        "eligibility_rules": {"min_income": 3000000}
      },
      "provenance": {"source": "bank_internal_policy", "created_at": "2026-01-01"}
    },
    {
      "type": "product",
      "data": {
        "product_id": "SME_LOAN_STANDARD",
        "constraints": {"max_amount": 500000000}
      },
      "provenance": {"source": "product_catalog"}
    },
    {
      "type": "rule_mapping",
      "data": {
        "mapping_id": "RULE_MAP_SME_LOAN_V1",
        "v1_required_fields": ["loan_amount", "beneficiary_name", "loan_contract_date"],
        "document_requirements": {"loan_application_form": true, "bank_statement": true}
      },
      "provenance": {"source": "core_binding_definition"}
    }
  ]
}
```

**Invariants that must be preserved:**
- `rule_mapping` **must always** be present in the output (mandatory).
- Every candidate **must** have `type` and `provenance`.
- HPVD **must not** modify the contents of `observed_data`.
- HPVD **must not** make decisions (allow/deny/conflict).

---

## 5. Retrieval Pipeline

```
Input (observed_data + metadata.sector)
    │
    ▼  Step 1: Sector Filter                    ~1ms
    │  knowledge_index.filter_by_sector(sector)
    │  → subset of all knowledge objects for this sector
    │
    ▼  Step 2: Field-Based Matching             ~5ms
    │  query_builder.extract_keywords(observed_data)
    │  → ["loan_amount", "income", ...]
    │  matcher.find(keywords, policy_feature_index)
    │  → relevant Policy + Product objects
    │
    ▼  Step 3: Mandatory Retrieval              ~1ms
    │  knowledge_index.get_rule_mapping(sector)
    │  → rule_mapping object (always included)
    │
    ▼  Step 4: Format as KnowledgeCandidates    ~1ms
    │  wrap each object → {type, data, provenance}
    │
Output: candidates list                total ~8ms
```

### Fallback logic

| Condition | Action |
|-----------|--------|
| Sector not found in Knowledge Layer | Return empty candidates (log warning) |
| No policy matches observed fields | Return rule_mapping only (mandatory) |
| Knowledge Layer empty | Return empty candidates + diagnostic flag |

---

## 6. Quality Gates & Test Scenarios

### 6.1 Knowledge Retrieval Test Scenarios

| Test | Scenario | What is validated |
|------|----------|-------------------|
| K1 | Sector match | Banking query → only banking objects are returned |
| K2 | Field match | `loan_amount` in observed → SME loan policy & product are returned |
| K3 | Mandatory rule_mapping | There is always a rule_mapping even if field matches are empty |
| K4 | Provenance completeness | All candidates have `type` and `provenance` |
| K5 | Empty sector | Unknown sector → empty candidates, no crash |
| K6 | Determinism | Same input → same candidates (order and content) |
| K7 | Pipeline integration | J13 → HPVDPipelineEngine → J14(knowledge) → J15 → J16 |

### 6.2 Quality Metrics Targets

| Metric | Target |
|--------|--------|
| Rule mapping recall | 100% (always returned) |
| Sector precision | 100% (no cross-sector leakage) |
| Query latency P95 | < 50ms |
| Provenance coverage | 100% (every candidate has provenance) |
| Determinism | Bitwise identical for same input |

### 6.3 Test Coverage (72 existing + new)

| File | Tests | Coverage |
|------|-------|---------|
| `test_contract.py` | 30 | Bundle validation, embedding lifecycle, serializer round-trip |
| `test_synthetic_scenarios.py` | 10 | T1–T8 epistemic scenarios (finance domain) |
| `test_embedding.py` | 7 | PCA fit/transform, save/load, determinism |
| `test_sparse_index.py` | 10 | Add/remove/filter, regime match scoring |
| `test_trajectory.py` | 13 | Trajectory creation, validation, DNA handling |
| `test_adapters.py` + `test_kl_integration.py` | 2 | Pipeline adapter, KL integration |
| `test_knowledge_retrieval.py` | 7+ | K1–K7 knowledge retrieval scenarios (new) |

---

## 7. Configuration Reference

### Knowledge Layer Parameters

| Parameter | Default | Description |
|-----------|---------|------------|
| `default_k` | 10 | Max candidates per type |
| `mandatory_types` | `["rule_mapping"]` | Always included in output |
| `sector_strict` | `True` | Reject cross-sector objects |
| `enable_feature_index` | `True` | Use policy_feature_index if available |

### Legacy Finance Parameters (FinanceRetrievalStrategy only)

| Parameter | Default | Description |
|-----------|---------|------------|
| `embedding_dim` | 256 | PCA output dimension |
| `trajectory_window` | 60 | Days per trajectory |
| `feature_count` | 45 | R45 features |
| `min_aci` | 0.7 | Minimum ACI threshold |

### Environment Variables

```bash
HPVD_DEFAULT_K=10
HPVD_SECTOR_STRICT=true
HPVD_MANDATORY_TYPES=rule_mapping
```

---

## 8. API Reference

### Primary API — Knowledge Retrieval

```python
from hpvd.adapters import HPVDPipelineEngine
from hpvd.adapters.strategies import KnowledgeRetrievalStrategy

# Build knowledge index dari corpus
strategy = KnowledgeRetrievalStrategy()
strategy.build_index(knowledge_corpus)   # List[dict] — Policy/Product/RuleMapping/DocumentSchema

# Via pipeline engine
pipeline = HPVDPipelineEngine()
pipeline.register_strategy(strategy)
pipeline.build_knowledge_index(knowledge_corpus)

# Process query
result = pipeline.process_query({
    "query_id": "REQ_001",
    "scope": {"domain": "knowledge"},
    "observed_data": {"loan_amount": 50000000, "income": 10000000},
    "sector": "banking"
})
# result.j14.candidates  → KnowledgeCandidate list
# result.j16.families    → grouped by type
```

### Multi-Strategy API (Knowledge + Finance)

```python
from hpvd.adapters.strategies import KnowledgeRetrievalStrategy, FinanceRetrievalStrategy

pipeline = HPVDPipelineEngine()
pipeline.register_strategy(KnowledgeRetrievalStrategy())
pipeline.register_strategy(FinanceRetrievalStrategy(config))

# Build indexes
pipeline.build_knowledge_index(knowledge_corpus)
pipeline.build_finance_index(trajectory_bundles)

# Dispatch is automatic based on scope.domain in J13
result_knowledge = pipeline.process_query({..., "scope": {"domain": "knowledge"}})
result_finance   = pipeline.process_query({..., "scope": {"domain": "finance"}})
```

### CLI

```powershell
# Build knowledge index dari folder JSON files
python -m src.hpvd.cli build-knowledge-index --corpus data/knowledge/ --output artifacts/

# Search (knowledge domain)
python -m src.hpvd.cli search --index artifacts/ --domain knowledge --query query.json
```

---

## 9. FinanceRetrievalStrategy Internals

> **Scope:** This section is only relevant for **capital markets / OHLCV time series** use cases. It is not the primary HPVD interface.

`FinanceRetrievalStrategy` is a domain strategy that wraps `HPVDEngine` for historical analog search based on a trajectory matrix.

### 9.1 Trajectory: 60 × 45 Matrix

Each trajectory represents **60 trading days × 45 engineered features (R45)**:

| Block | Features | Count | Description |
|-------|----------|-------|-----------|
| A | Returns | 8 | 1d/5d/10d/20d returns (plain & log) |
| B | Trend | 10 | Slopes, R², MA crossovers |
| C | Volatility | 12 | Realized vol, ATR, shocks, gaps |
| D | Price Structure | 10 | Candle patterns, skew, kurtosis |
| E | Regime | 5 | Trend/vol/momentum/structure regimes |
| **Total** | | **45** | |

### 9.2 HPVDInputBundle — Finance-Only Contract

`HPVDInputBundle` is the input container for `FinanceRetrievalStrategy`. It is not used by `KnowledgeRetrievalStrategy`.

```json
{
  "trajectory": [[0.1, 0.2, "..."], ["..."]],
  "dna": [0.5, -0.3, "..."],
  "geometry_context": {"LTV": 0.3, "LVC": 0.1, "K": 5.0},
  "metadata": {
    "trajectory_id": "traj_0001",
    "regime_id": "R1",
    "schema_version": "hpvd_input_v1",
    "timestamp": "2024-01-15T00:00:00+00:00"
  }
}
```

### 9.3 Hybrid Distance Formula

```
fused_dist  = 0.7 × hybrid_dist + 0.3 × dna_distance
confidence  = max(0, 1 - min(fused_dist, 1))
```

### 9.4 Legacy API (untuk FinanceRetrievalStrategy)

```python
from hpvd import HPVDEngine, HPVDInputBundle, HPVD_Output

engine = HPVDEngine()
engine.build_from_bundles(list_of_bundles)
output: HPVD_Output = engine.search_families(query_bundle)
d = output.to_dict()
```

---

*Version 1.0.0-alpha2 | Manithy v1 — Deterministic Attestation System*
