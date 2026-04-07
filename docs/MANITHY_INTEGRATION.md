# Manithy Integration Guide

> This document explains the role of HPVD in the **Manithy v1** pipeline — a multi-sector Deterministic Attestation system (Banking, Finance, Chatbot) — covering HPVD’s position in NRB, multi-strategy architecture, J-files reference, VectorState format (Core layer), and Knowledge Layer integration.

---

## Table of Contents

1. [Manithy Pipeline Overview](#1-manithy-pipeline-overview)
2. [HPVD in the Pipeline — NRB Stage](#2-hpvd-in-the-pipeline--nrb-stage)
3. [Multi-Domain Strategy Architecture](#3-multi-domain-strategy-architecture)
4. [J-Files Reference](#4-j-files-reference)
5. [VectorState Format (Core Layer — J06)](#5-vectorstate-format-core-layer--j06)
6. [Knowledge Layer Integration](#6-knowledge-layer-integration)

---

## 1. Manithy Pipeline Overview

The Manithy v1 pipeline is structured into two major domains separated by the `t-1` boundary:

```
[ INPUT ]
    │  request_id + sector + files
    ▼
┌─────────────────────────────────────────────────────────────────┐
│ NRB — Non-Binding Realm                                         │
│                                                                 │
│  ┌────────────────┐    ┌──────────────────┐                     │
│  │ 1. Parser      │───▶│ 2. HPVD          │                     │
│  │ (sector-spec)  │    │ (knowledge       │◀── Knowledge Layer   │
│  │                │    │  retrieval)      │    Policy/Product/   │
│  │ → observed_data│    │ → candidates     │    RuleMapping       │
│  └────────────────┘    └────────┬─────────┘                     │
│                                 │                               │
│                        ┌────────▼─────────┐                     │
│                        │ 3. PMR           │                     │
│                        │ → hypotheses     │                     │
│                        └────────┬─────────┘                     │
│                                 │                               │
│                        ┌────────▼─────────┐                     │
│                        │ 4. Knowledge     │                     │
│                        │    Builder       │                     │
│                        │ KNOWN/UNKNOWN/   │                     │
│                        │ CONFLICT         │                     │
│                        └────────┬─────────┘                     │
└─────────────────────────────────┼───────────────────────────────┘
                                  │
                     ┌────────────▼──────────────┐
                     │ BOUNDARY  t-1             │
                     │ (freeze observed_state)   │
                     └────────────┬──────────────┘
                                  │
┌─────────────────────────────────▼───────────────────────────────┐
│ RB CORE — Binding Domain                                        │
│                                                                 │
│  J01 → J02 → J03(CCR) → J04 → J05(StructuredCtx)              │
│  → J06(VectorState) → J07(Trajectory)                          │
│  → J08(V1 Coverage) → J09(EFV) → J10(V3 Decision)             │
│  → J11(EvidencePack) → J12(FactsEnvelope)                      │
│  → J13(PostCoreQuery — downstream trigger)                     │
│                                                                 │
│  Multi-Manifold + Geometry (DGG/AIR) setelah J06               │
└─────────────────────────────────────────────────────────────────┘
                                  │
                     ┌────────────▼──────────────┐
                     │ OUTPUT                    │
                     │ Decision + Evidence Pack  │
                     └───────────────────────────┘
```

**Summary of components per layer:**

| Layer | Component | Input | Output |
|-------|----------|-------|--------|
| NRB | Parser | request + files | observed_data + documents |
| NRB | **HPVD** | observed_data + sector | candidates [{type, data, provenance}] |
| NRB | PMR | observed_data + candidates | hypotheses |
| NRB | Knowledge Builder | observed_data + hypotheses | KNOWN/UNKNOWN/CONFLICT |
| Boundary | Producer t-1 | epistemic state | frozen observed_state |
| Core | Adapter (CCR) | observed_state | structured representation |
| Core | VectorState (J06) | structured representation | binary feature vector |
| Core | V1 (J08) | VectorState + availability | COVERED / UNCOVERED |
| Core | V3 (J10) | V1 result + rules | PERMIT / BLOCK / NOT_EVALUATED |
| Core | Evidence Pack (J11) | decision + hash chain | proof artifact |

**Important notes:**
- HPVD operates in **NRB**, before Core, not after Core.
- `J13 (PostCoreQuery)` in the Core spec is the trigger for downstream after Core completes — this is DIFFERENT from J13 in `HPVDPipelineEngine` (which is the incoming query format to the HPVD adapter layer).
- HPVD does not make decisions. Its output is candidates to be processed by PMR.

---

## 2. HPVD in the Pipeline — NRB Stage

### NRB Step 1 — Parser (Sector-Specific)

The Parser receives request + files and produces `observed_data`:

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

The Parser is sector-specific (`ParserBanking`, `ParserChatbot`, `ParserFinance`). NRBOrchestrator selects the parser based on the `sector` from the request.

### NRB Step 2 — HPVD (Knowledge Retrieval)

HPVD receives `observed_data + metadata.sector` from the Parser and retrieves relevant knowledge from the Knowledge Layer.

**Three internal stages in HPVD:**

1. **Sector Filter** — retrieve all knowledge objects with matching `sector`
2. **Field-Based Matching** — match fields in `observed_data` (e.g., `loan_amount`, `income`) with the policy feature index
3. **Mandatory Retrieval** — always include the `rule_mapping` that matches the sector

**HPVD Output:**

```json
{
  "candidates": [
    {
      "type": "policy",
      "data": {
        "policy_id": "POLICY_SME_LOAN_V1",
        "required_documents": ["loan_application_form", "identity_document", "bank_statement", "financial_statement"],
        "eligibility_rules": {"min_income": 3000000, "min_age": 21}
      },
      "provenance": {"source": "bank_internal_policy", "created_at": "2026-01-01"}
    },
    {
      "type": "product",
      "data": {
        "product_id": "SME_LOAN_STANDARD",
        "loan_constraints": {"min_amount": 5000000, "max_amount": 500000000}
      },
      "provenance": {"source": "product_catalog"}
    },
    {
      "type": "rule_mapping",
      "data": {
        "mapping_id": "RULE_MAP_SME_LOAN_V1",
        "v1_required_fields": ["loan_amount", "beneficiary_name", "loan_contract_date"],
        "v3_required_fields": ["loan_amount", "income", "dti_ratio"],
        "document_requirements": {
          "loan_application_form": "doc_application_present",
          "bank_statement": "doc_bank_statement_present"
        }
      },
      "provenance": {"source": "core_binding_definition"}
    }
  ]
}
```

### NRB Step 3 — PMR (Hypothesis Construction)

PMR receives `observed_data + candidates` and builds hypotheses:
- Which fields are supposed to be present (from rule_mapping)?
- What is present vs missing?

### NRB Step 4 — Knowledge Builder (Epistemic Structuring)

Knowledge Builder produces the epistemic state:

```json
{
  "KNOWN": {"applicant_name": "Budi Santoso", "loan_amount": 50000000, "income": 10000000},
  "UNKNOWN": ["beneficiary_name", "loan_contract_date", "financial_statement"],
  "CONFLICT": []
}
```

---

## 3. Multi-Domain Strategy Architecture

HPVD is a retrieval layer that dispatches to different strategies based on `scope.domain` in J13.

```
┌───────────────────────────────────────────────────────┐
│              HPVDPipelineEngine                       │
│         (unified: J13 → J14 / J15 / J16)             │
├──────────────────┬────────────────────────────────────┤
│  StrategyDispatcher (domain → strategy)               │
└──────┬───────────┬──────────────┬─────────────────────┘
       │           │              │
  ┌────▼────┐ ┌────▼────┐  ┌─────▼──────┐
  │Knowledge│ │ Finance │  │  Document  │
  │Strategy │ │Strategy │  │  Strategy  │
  │         │ │         │  │            │
  │Sector   │ │HPVDCore │  │Sentence-   │
  │Filter + │ │(60×45)  │  │Transformer │
  │Field    │ │+ FAISS  │  │+ FAISS     │
  │Matching │ │         │  │            │
  └────┬────┘ └────┬────┘  └─────┬──────┘
       │           │              │
       J14         J14            J14    ← KnowledgeCandidate list
       J15         J15            J15    ← filtered candidates
       J16         J16            J16    ← grouped by type/family
```

**Principles:**
- Input contract is the same: J13 (`query_id`, `scope.domain`, `observed_data` / `query_payload`)
- Output contract is the same: J14/J15/J16
- `KnowledgeRetrievalStrategy` — **primary strategy** for Banking/Finance/Chatbot sector use cases
- `FinanceRetrievalStrategy` — for capital markets / OHLCV time series use cases (market data)
- `DocumentRetrievalStrategy` — for full-text document retrieval
- The non-binding principle applies to all strategies

### Concept Mapping: Knowledge ↔ Finance ↔ Document

| Concept | Knowledge | Finance (Market Data) | Document |
|--------|-----------|-----------------------|----------|
| Input | observed_data + sector | 60×45 trajectory matrix | Text / chunks |
| Embedding | Field keywords | PCA → 256-d | Sentence-transformer → 384-d |
| Pre-filter | Sector tag | Regime tuple | Topic category |
| Match logic | Field-based + sector | Euclidean + Cosine + Temporal | Cosine similarity |
| Output type | Policy/Product/RuleMapping | Analog trajectory | Document chunk |
| "Family" / group | By candidate type | By regime coherence | By topic |
| Outcome-blind | ✅ | ✅ | ✅ |

---

## 4. J-Files Reference

### J13 — Knowledge Query (input to HPVDPipelineEngine)

> **Note:** In this codebase, J13 is the incoming query format to `HPVDPipelineEngine`, not the Core layer "PostCoreQuery". The name is kept for backward compatibility.

```json
{
  "schema_id": "manithy.post_core_query.v2",
  "query_id": "REQ_LOAN_0001",
  "scope": {
    "domain": "knowledge"
  },
  "observed_data": {
    "applicant_name": "Budi Santoso",
    "loan_amount": 50000000,
    "income": 10000000
  },
  "sector": "banking",
  "allowed_topics": [],
  "allowed_corpora": [],
  "allowed_doc_types": []
}
```

Fields `observed_data` and `sector` were added in Manithy v1. Legacy fields (`query_payload`, `allowed_topics`, `allowed_corpora`) are kept for backward compatibility with `FinanceRetrievalStrategy` and `DocumentRetrievalStrategy`.

### J14 — RetrievalRaw (KnowledgeRetrievalStrategy output)

```json
{
  "schema_id": "manithy.hpvd_retrieval_raw.v1",
  "query_id": "REQ_LOAN_0001",
  "domain": "knowledge",
  "candidates": [
    {
      "type": "policy",
      "data": {
        "policy_id": "POLICY_SME_LOAN_V1",
        "sector": "banking",
        "required_documents": ["loan_application_form", "identity_document"]
      },
      "provenance": {"source": "bank_internal_policy", "created_at": "2026-01-01"}
    },
    {
      "type": "rule_mapping",
      "data": {
        "mapping_id": "RULE_MAP_SME_LOAN_V1",
        "v1_required_fields": ["loan_amount", "beneficiary_name"]
      },
      "provenance": {"source": "core_binding_definition"}
    }
  ],
  "diagnostics": {
    "sector_matched": "banking",
    "objects_considered": 7,
    "objects_returned": 3,
    "rule_mapping_forced": true,
    "latency_ms": 8.2
  }
}
```

### J15 — PhaseFilteredSet (sector/type filtered candidates)

```json
{
  "schema_id": "manithy.phase_filtered_set.v1",
  "query_id": "REQ_LOAN_0001",
  "accepted": [
    {
      "type": "policy",
      "data": {"policy_id": "POLICY_SME_LOAN_V1"},
      "provenance": {"source": "bank_internal_policy"}
    }
  ],
  "rejected": [],
  "filter_criteria": {
    "sector": "banking",
    "allowed_types": ["policy", "product", "rule_mapping"]
  }
}
```

### J16 — KnowledgePackage (grouped by type)

```json
{
  "schema_id": "manithy.analog_family_assignment.v1",
  "query_id": "REQ_LOAN_0001",
  "families": [
    {
      "family_id": "knowledge_policy",
      "members": [
        {"type": "policy", "data": {"policy_id": "POLICY_SME_LOAN_V1"}, "provenance": {...}}
      ],
      "coherence": {"mean_confidence": 1.0, "dispersion": 0.0, "size": 1},
      "structural_signature": {"phase": "policy_group"},
      "uncertainty_flags": {"phase_boundary": false, "weak_support": false, "partial_overlap": false}
    },
    {
      "family_id": "knowledge_rule_mapping",
      "members": [
        {"type": "rule_mapping", "data": {"mapping_id": "RULE_MAP_SME_LOAN_V1"}, "provenance": {...}}
      ],
      "coherence": {"mean_confidence": 1.0, "dispersion": 0.0, "size": 1},
      "structural_signature": {"phase": "rule_mapping_group"},
      "uncertainty_flags": {"phase_boundary": false, "weak_support": false, "partial_overlap": false}
    }
  ],
  "total_members": 3,
  "total_families": 2,
  "metadata": {"domain": "knowledge", "sector": "banking"}
}
```

> **J16 Note:** `schema_id` is left as `manithy.analog_family_assignment.v1` for backward compatibility with existing code. In the knowledge context, each "family" is a group of candidates with the same type (policy/product/rule_mapping).

---

## 5. VectorState Format (Core Layer — J06)

> **Important:** VectorState is the output of the **Adapter in the Core layer** (J06), NOT the output of HPVD. VectorState is created AFTER the t-1 boundary, from the `observed_state` that has been frozen.

VectorState is a binary representation of the observed_state for evaluation by V1 (Coverage) and V3 (Decision).

### 5.1 Metadata (kernel identity)

```yaml
meta:
  vector_schema_version: "v2"
  ruleset_version: "r1"
  policy_bundle_version: "p1"
  commit_id: "sha256_..."
  tenant_id: "banking_core | chatbot_eu | finance_desk"
  action_class: "loan_application | refund | trade_execution"
```

### 5.2 Authority Identity

```yaml
authority_identity:
  channel: ENUM        # WEB | SYSTEM | API
  actor_role: ENUM     # CUSTOMER | OPERATOR | SYSTEM
  auth_level: ENUM
  session_trust_level: ENUM
```

### 5.3 Intent

```yaml
intent:
  action_kind: "LOAN_SUBMISSION | REFUND | TRADE_EXECUTION"
  subject_key: "APPLICATION_8891 | ORDER_67250"
  irreversible: true
```

### 5.4 Domain State (per sector)

**Banking/Loan:**
```yaml
domain_state:
  p0.metrics: {requested_amount_minor, income_minor, debt_ratio}
  p0.flags:   {collateral_present}
  availability:
    income_verified: true
    bureau_data_known: false
    collateral_valuation_known: false
  unknown_bitmap: "010011"
```

**Chatbot/Refund:**
```yaml
domain_state:
  p0.metrics: {amount_minor}
  p0.flags:   {customer_present, operator_initiated}
  availability:
    original_payment_state_known: true
    psp_refund_capability_known: false
```

**Finance (Market Data):**
```yaml
domain_state:
  p0.metrics: {rv_short, rv_long, vol_ratio, amihud_illiquidity}
  p0.flags:   {proc_fail}
  p1.metrics: {K, LCV, LTV, entropy_density}
  availability: {liquidity_proxy_known, volatility_structure_known}
```

### 5.5 Relationship between VectorState and HPVD

```
NRB:
  observed_data (raw fields: loan_amount=50M, income=10M)
  → HPVD → candidates (policy: min_income=3M, rule_mapping: v1_fields=[...])
  → PMR → hypotheses
  → Knowledge Builder → KNOWN/UNKNOWN/CONFLICT

Boundary t-1: freeze

Core (J06 — VectorState):
  observed_state + availability bitmap
  income_above_min: true   ← derived from KNOWN + policy rule
  employment_known: false  ← dari UNKNOWN
  identity_verified: false ← dari UNKNOWN
```

HPVD retrieves `policy` and `rule_mapping` which are then — via PMR and Knowledge Builder — used as references to populate availability fields in VectorState. HPVD itself does not write to VectorState.

---

## 6. Knowledge Layer Integration

### 6.1 Role of the Knowledge Layer in Manithy v1

The Knowledge Layer is the source of truth for all knowledge objects retrieved by HPVD. In the MVP (Knowledge Starter), the Knowledge Layer contains:

| Type | Example | Used by |
|------|--------|-------------|
| Policy | `policy_sme_loan_v1.json` | HPVD (Step 2 field matching) |
| Product | `product_sme_loan_standard.json` | HPVD (Step 2 field matching) |
| Document Schema | `doc_loan_application.json` | Parser + HPVD |
| Rule Mapping | `rule_mapping_sme_loan.json` | HPVD (Step 3 mandatory) |
| Policy Feature Index | `policy_feature_index.json` | HPVD (Step 2 acceleration) |

In the Knowledge Starter (MVP), there are not yet:
- Historical cases
- Risk models
- Learned patterns

### 6.2 Knowledge Layer — File Structure (Starter)

```
knowledge_layer/
├── banking/
│   ├── policy_sme_loan_v1.json
│   ├── product_sme_loan_standard.json
│   ├── rule_mapping_sme_loan_v1.json
│   ├── doc_loan_application.json
│   ├── doc_identity.json
│   ├── doc_bank_statement.json
│   └── policy_feature_index.json
├── chatbot/
│   ├── policy_refund_v1.json
│   └── rule_mapping_refund_v1.json
└── finance/
    └── (future: market data policies)
```

### 6.3 NRBOrchestrator + HPVD Integration

```python
class NRBOrchestrator:
    def run_nrb(self, request):
        # 1. Resolve parser by sector
        parser = self.parser_registry.get(request["sector"])

        # 2. Parse (sector-specific)
        parsed = parser.parse(request)
        # parsed = {observed_data, documents, metadata}

        # 3. HPVD retrieve (generic, sector-agnostic)
        candidates = self.hpvd.retrieve(
            observed=parsed["observed_data"],
            sector=parsed["metadata"]["sector"]
        )
        # candidates = [{type, data, provenance}, ...]

        # 4. PMR build hypotheses
        hypotheses = self.pmr.build(
            observed=parsed["observed_data"],
            candidates=candidates
        )

        # 5. Knowledge Builder
        knowledge = self.knowledge_builder.build(
            observed=parsed["observed_data"],
            hypotheses=hypotheses
        )

        return {"parsed": parsed, "candidates": candidates,
                "hypotheses": hypotheses, "knowledge": knowledge}
```

### 6.4 Gap Analysis (KL Production)

| # | Gap | Severity | Status | Impact on HPVD |
|:-:|-----|:--------:|--------|----------------|
| G1 | Sector-based storage & retrieval | 🔴 Critical | MVP: in-memory | HPVD must load from files per sector |
| G2 | Policy versioning | 🟠 High | Not yet available | HPVD cannot resolve policy versions |
| G3 | Structured metadata (sector, product_type) | 🟠 High | Partial | Candidate pool filtering is limited |
| G4 | Search / query endpoint | 🟡 Medium | Not yet available | Must fetch all objects and filter client-side |
| G5 | Snapshot pinning | 🟡 Medium | Not yet available | Determinism cannot be enforced across requests |

**KL implementation priorities:**
1. **MVP (current):** In-memory load from JSON files per sector
2. **Phase 1:** REST API with endpoint `GET /knowledge?sector=banking&type=policy`
3. **Phase 2:** Versioning + snapshot pinning
4. **Phase 3:** Semantic search endpoint

---

*Last updated: 2026-04-01 | Manithy v1 — Deterministic Attestation System*
