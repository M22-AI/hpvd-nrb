# Manithy Integration Guide

> Dokumen ini menjelaskan peran HPVD dalam pipeline **Manithy v1** — sistem Deterministic Attestation multi-sektor (Banking, Finance, Chatbot) — mencakup posisi HPVD di NRB, arsitektur multi-strategy, J-files reference, VectorState format (Core layer), dan integrasi Knowledge Layer.

---

## Daftar Isi

1. [Manithy Pipeline Overview](#1-manithy-pipeline-overview)
2. [HPVD dalam Pipeline — NRB Stage](#2-hpvd-dalam-pipeline--nrb-stage)
3. [Multi-Domain Strategy Architecture](#3-multi-domain-strategy-architecture)
4. [J-Files Reference](#4-j-files-reference)
5. [VectorState Format (Core Layer — J06)](#5-vectorstate-format-core-layer--j06)
6. [Knowledge Layer Integration](#6-knowledge-layer-integration)

---

## 1. Manithy Pipeline Overview

Pipeline Manithy v1 tersusun menjadi dua domain besar yang dipisahkan oleh boundary `t-1`:

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

**Ringkasan komponen per layer:**

| Layer | Komponen | Input | Output |
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

**Catatan penting:**
- HPVD beroperasi di **NRB**, sebelum Core, bukan setelah Core.
- `J13 (PostCoreQuery)` di Core spec adalah trigger untuk downstream setelah Core selesai — ini BERBEDA dengan J13 di `HPVDPipelineEngine` (yang adalah query format masuk ke adapter layer HPVD).
- HPVD tidak membuat keputusan. Output-nya adalah candidates yang akan diproses PMR.

---

## 2. HPVD dalam Pipeline — NRB Stage

### NRB Step 1 — Parser (Sector-Specific)

Parser menerima request + files dan menghasilkan `observed_data`:

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

Parser adalah sector-specific (`ParserBanking`, `ParserChatbot`, `ParserFinance`). NRBOrchestrator memilih parser berdasarkan `sector` dari request.

### NRB Step 2 — HPVD (Knowledge Retrieval)

HPVD menerima `observed_data + metadata.sector` dari Parser dan me-retrieve knowledge yang relevan dari Knowledge Layer.

**3 tahap internal HPVD:**

1. **Sector Filter** — ambil semua knowledge objects dengan matching `sector`
2. **Field-Based Matching** — cocokkan field di `observed_data` (e.g., `loan_amount`, `income`) dengan policy feature index
3. **Mandatory Retrieval** — selalu sertakan `rule_mapping` yang cocok dengan sektor

**Output HPVD:**

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

PMR menerima `observed_data + candidates` dan membangun hypotheses:
- Apa field yang seharusnya ada (dari rule_mapping)?
- Apa yang present vs missing?

### NRB Step 4 — Knowledge Builder (Epistemic Structuring)

Knowledge Builder menghasilkan epistemic state:

```json
{
  "KNOWN": {"applicant_name": "Budi Santoso", "loan_amount": 50000000, "income": 10000000},
  "UNKNOWN": ["beneficiary_name", "loan_contract_date", "financial_statement"],
  "CONFLICT": []
}
```

---

## 3. Multi-Domain Strategy Architecture

HPVD adalah retrieval layer yang di-dispatch ke strategy berbeda berdasarkan `scope.domain` di J13.

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

**Prinsip:**
- Input contract sama: J13 (`query_id`, `scope.domain`, `observed_data` / `query_payload`)
- Output contract sama: J14/J15/J16
- `KnowledgeRetrievalStrategy` — **primary strategy** untuk Banking/Finance/Chatbot sector use cases
- `FinanceRetrievalStrategy` — untuk capital markets / OHLCV time series use cases (market data)
- `DocumentRetrievalStrategy` — untuk full-text document retrieval
- Non-binding principle berlaku di semua strategy

### Concept Mapping: Knowledge ↔ Finance ↔ Document

| Konsep | Knowledge | Finance (Market Data) | Document |
|--------|-----------|----------------------|----------|
| Input | observed_data + sector | 60×45 trajectory matrix | Text / chunks |
| Embedding | Field keywords | PCA → 256-d | Sentence-transformer → 384-d |
| Pre-filter | Sector tag | Regime tuple | Topic category |
| Match logic | Field-based + sector | Euclidean + Cosine + Temporal | Cosine similarity |
| Output type | Policy/Product/RuleMapping | Analog trajectory | Document chunk |
| "Family" / group | By candidate type | By regime coherence | By topic |
| Outcome-blind | ✅ | ✅ | ✅ |

---

## 4. J-Files Reference

### J13 — Knowledge Query (input ke HPVDPipelineEngine)

> **Catatan:** J13 di codebase ini adalah format query masuk ke `HPVDPipelineEngine`, bukan "PostCoreQuery" Core layer. Nama tetap dipertahankan untuk backward compatibility.

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

Fields `observed_data` dan `sector` ditambahkan di Manithy v1. Fields lama (`query_payload`, `allowed_topics`, `allowed_corpora`) tetap ada untuk backward compatibility dengan `FinanceRetrievalStrategy` dan `DocumentRetrievalStrategy`.

### J14 — RetrievalRaw (output KnowledgeRetrievalStrategy)

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

> **Catatan J16:** `schema_id` dibiarkan `manithy.analog_family_assignment.v1` untuk backward compatibility dengan kode yang sudah ada. Dalam knowledge context, setiap "family" adalah group of candidates dengan tipe yang sama (policy/product/rule_mapping).

---

## 5. VectorState Format (Core Layer — J06)

> **Penting:** VectorState adalah output dari **Adapter di Core layer** (J06), BUKAN output HPVD. VectorState dibuat SETELAH boundary t-1, dari `observed_state` yang sudah di-freeze.

VectorState adalah representasi biner dari observed_state untuk evaluasi oleh V1 (Coverage) dan V3 (Decision).

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

### 5.5 Relasi VectorState dan HPVD

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

HPVD mengambil `policy` dan `rule_mapping` yang kemudian — melalui PMR dan Knowledge Builder — dipakai sebagai referensi untuk mengisi field availability di VectorState. HPVD sendiri tidak menulis ke VectorState.

---

## 6. Knowledge Layer Integration

### 6.1 Peran Knowledge Layer dalam Manithy v1

Knowledge Layer adalah source-of-truth untuk semua knowledge objects yang di-retrieve oleh HPVD. Dalam MVP (Knowledge Starter), Knowledge Layer berisi:

| Tipe | Contoh | Dipakai oleh |
|------|--------|-------------|
| Policy | `policy_sme_loan_v1.json` | HPVD (Step 2 field matching) |
| Product | `product_sme_loan_standard.json` | HPVD (Step 2 field matching) |
| Document Schema | `doc_loan_application.json` | Parser + HPVD |
| Rule Mapping | `rule_mapping_sme_loan.json` | HPVD (Step 3 mandatory) |
| Policy Feature Index | `policy_feature_index.json` | HPVD (Step 2 acceleration) |

Pada Knowledge Starter (MVP), belum ada:
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

| # | Gap | Severity | Status | Dampak ke HPVD |
|:-:|-----|:--------:|--------|----------------|
| G1 | Sector-based storage & retrieval | 🔴 Critical | MVP: in-memory | HPVD harus load dari file per sektor |
| G2 | Policy versioning | 🟠 High | Belum ada | HPVD tidak bisa resolve versi policy |
| G3 | Structured metadata (sector, product_type) | 🟠 High | Parsial | Filtering candidate pool terbatas |
| G4 | Search / query endpoint | 🟡 Medium | Belum ada | Harus fetch semua objects, filter di client |
| G5 | Snapshot pinning | 🟡 Medium | Belum ada | Determinism tidak bisa di-enforce cross-request |

**Prioritas implementasi KL:**
1. **MVP (saat ini):** In-memory load dari JSON files per sektor
2. **Fase 1:** REST API dengan endpoint `GET /knowledge?sector=banking&type=policy`
3. **Fase 2:** Versioning + snapshot pinning
4. **Fase 3:** Semantic search endpoint

---

*Last updated: 2026-04-01 | Manithy v1 — Deterministic Attestation System*
