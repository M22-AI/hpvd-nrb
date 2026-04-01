# Manithy Integration Guide

> Dokumen ini menjelaskan peran HPVD dalam pipeline **Manithy** — sistem reasoning multi-domain (Finance, Chatbot/Refund, Banking/Loan) — mencakup arsitektur multi-domain, J-files reference, VectorState format, dan integrasi Knowledge Layer.

---

## Daftar Isi

1. [Manithy Pipeline Overview](#1-manithy-pipeline-overview)
2. [HPVD dalam Pipeline (Stage 11–16)](#2-hpvd-dalam-pipeline-stage-1116)
3. [Multi-Domain Strategy Architecture](#3-multi-domain-strategy-architecture)
4. [J-Files Reference](#4-j-files-reference)
5. [VectorState Format (J06)](#5-vectorstate-format-j06)
6. [KL Integration](#6-kl-integration)

---

## 1. Manithy Pipeline Overview

Pipeline Manithy terdiri dari **18 stage** yang mentransformasi input mentah menjadi penjelasan berbasis structured reasoning.

```
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 1. INPUT     │──▶│ 2. SNAPSHOT  │──▶│ 3. METADATA  │──▶│ 4. CCR       │
│  (Adapter)   │   │  (Immutable) │   │  (J01)       │   │  (J03)       │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
                                                                 │
       ┌─────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 5. PROJECT   │──▶│ 6. COVERAGE  │──▶│ 7. RULES     │──▶│ 8. SEAL      │
│  (J05+J06)   │   │  V1 (J08)   │   │  V3 (J09)    │   │  (J11/J12)   │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
                                                                 │
       ┌─────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ 9. FINGERPRNT│──▶│10. REPLAYABLE│──▶│11. SERVING   │──▶│12. KNOWLEDGE │
│  (J20)       │   │  (Audit)     │   │ ADAPTER(J13) │   │  SNAPSHOT    │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
                                                                 │
       ┌─────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│13. HPVD      │──▶│14. PHASE     │──▶│15. ANALOG    │──▶│16. PMR GRAPH │
│ RETRIEVAL(J14)   │ FILTER (J15) │   │ FAMILY (J16) │   │  (J17)       │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
                                                                 │
       ┌─────────────────────────────────────────────────────────┘
       ▼
┌──────────────┐   ┌──────────────┐
│17. REASONING │──▶│18. LLM RENDER│
│ OUTPUT (J18) │   │  (J19)       │
└──────────────┘   └──────────────┘
```

**Ringkasan stage per J-file:**

| Stage | J-File | Deskripsi |
|-------|--------|-----------|
| 3 | J01 | CommitBoundaryEvent — identitas kasus + boundary |
| 3 | J02 | PackInit — diagnostic/opsional |
| 4 | J03 | CCR (Canonical Case Record) — kasus terstruktur |
| 4 | J04 | CaptureReceipt — opsional |
| 5 | J05 | StructuredContext — authority + intent extracted |
| 5 | J06 | VectorState — representasi vektor lengkap |
| 5 | J07 | Trajectory tracking — opsional |
| 6 | J08 | L1_Admissibility — `COVERED` / `UNCOVERED` |
| 7 | J09 | EligibilityFeatureVector (EFV) — domain features |
| 7 | J10 | AuthorityAttestationToken — `PERMIT`/`BLOCK`/`REQUIRE_OVERRIDE` |
| 8 | J11 | EvidencePack — merkle tree |
| 8 | J12 | V2_FactsEnvelope — facts + pack_ref |
| 11 | J13 | PostCoreQuery — trigger HPVD |
| 13 | J14 | HPVD_RetrievalRaw — candidates + similarity |
| 14 | J15 | PhaseFilteredSet — accepted/rejected |
| 15 | J16 | AnalogFamilyAssignment — family + probability |
| 16 | J17 | PMR_HypothesisGraph — support/contradiction nodes |
| 17 | J18 | StructuredReasoningOutput — final reasoning object |
| 18 | J19 | Renderer_Output — LLM explanation text |
| 9/10 | J20 | ReplayReport — audit verification |

---

## 2. HPVD dalam Pipeline (Stage 11–16)

### Stage 11 — Serving Adapter → J13

Serving layer menerima J12 (EvidencePack) dan menghasilkan **J13 (PostCoreQuery)** — trigger untuk HPVD. J13 tidak mengubah keputusan; hanya mempersiapkan data untuk analog reasoning.

### Stage 12 — Knowledge Snapshot Pin

HPVD menerima `pinset_snapshot_id` dari J13 dan me-resolve ke:
- `dataset_snapshot_id` — snapshot historis yang digunakan
- `ontology_version` — versi ontologi
- `calibration_model_version` — versi model kalibrasi

### Stage 13 — HPVD Retrieval → J14

Structural-first analog retrieval. HPVD mencari kasus historis yang secara struktur mirip berdasarkan `action_class`, `vector geometry`, domain.

### Stage 14 — Phase Consistency Filter → J15

Memastikan analog dibandingkan pada **fase lifecycle yang sama**. Contoh: `TRADE_EXECUTION` tidak boleh dibandingkan dengan `REFUND` atau `LOAN_SUBMISSION`.

### Stage 15 — Analog Family Formation → J16

Mengelompokkan candidates ke dalam **Analog Families** dengan `membership_probability` dan historical outcome distribution.

### Stage 16 — PMR Hypothesis Graph → J17

PMR membangun hypothesis graph: nodes support/contradiction, overall_confidence, confidence interval.

---

## 3. Multi-Domain Strategy Architecture

HPVD di Manithy bukan satu engine monolitik — ia adalah **retrieval layer** yang di-dispatch ke strategy berbeda per domain.

```
┌──────────────────────────────────────────────┐
│          HPVDPipelineEngine                   │
│         (unified J13 → J14/J15/J16)           │
├──────────────┬──────────────┬─────────────────┤
│  Strategy    │  Dispatcher  │                 │
└──────┬───────┴──────┬───────┘                 │
       │              │                         │
  ┌────▼────┐  ┌──────▼──────┐                  │
  │ Finance │  │  Document   │                  │
  │Strategy │  │  Strategy   │                  │
  │         │  │             │                  │
  │HPVD Core│  │Sentence-    │                  │
  │(60×45)  │  │Transformer  │                  │
  │+ FAISS  │  │+ FAISS      │                  │
  └────┬────┘  └──────┬──────┘                  │
       │              │                         │
       J14            J14   ← output            │
       J15            J15   ← contract          │
       J16            J16   ← sama              │
```

**Prinsip:**
- Input contract sama: J13
- Output contract sama: J14/J15/J16
- HPVD Core (trajectory 60×45) dipakai **Finance domain saja**
- Domain lain (Chatbot, Banking) pakai DocumentRetrievalStrategy
- Outcome-blind principle berlaku di **semua** strategy

### Concept Mapping: Finance ↔ Document

| Konsep | Finance (Trajectory) | Document (Chatbot/Banking) |
|--------|---------------------|---------------------------|
| Input | 60×45 matrix, fixed shape | Teks variabel |
| Embedding | PCA → 256-d | Sentence-transformer → 384-d |
| Pre-filter key | Regime tuple `(trend, vol, struct)` | Topic category string |
| Pre-filter index | SparseRegimeIndex | Topic inverted index |
| Dense search | FAISS on 256-d | FAISS on 384-d (cosine) |
| Distance | Euclidean + Cosine + Temporal | Cosine only (temporal ❌) |
| Phase identity | DNA 16-d (continuous) | Doc-type (categorical) |
| Family grouping | Regime coherence | Topic/semantic coherence |
| Uncertainty flags | `weak_support`, `partial_overlap` | Same flags, same semantics |
| calibrated_similarity | Structural compatibility | Semantic compatibility |
| Outcome-blind | ✅ | ✅ |

---

## 4. J-Files Reference

### J12 — V2_FactsEnvelope (input ke Serving Adapter)

```json
{
  "kind": "J12.V2_FactsEnvelope",
  "schema_id": "manithy.v2.facts_envelope.v2",
  "pack_ref": {
    "pack_id": "<TENANT>:<SUBJECT>:<SEQ>",
    "hash_root": "sha256_merkle_root",
    "pinset_snapshot_id": "PINSET_2026W06"
  },
  "facts": {
    "event_class": "TRADE_EXECUTION | PAYMENT_REFUND | LOAN_SUBMISSION",
    "ep": "COVERED | UNCOVERED",
    "aat": "PERMIT | BLOCK | REQUIRE_OVERRIDE | NOT_EVALUATED"
  }
}
```

### J13 — PostCoreQuery (trigger HPVD)

```json
{
  "schema_id": "manithy.post_core_query.v2",
  "binding": "NON_BINDING",
  "query_id": "Q_TRADE_EXECUTION_SUPPORT",
  "query_version": 1,
  "opaque_pack_ref": {
    "pack_id": "pack_01...",
    "pinset_snapshot_id": "pinset_finance.v1#snap_N"
  },
  "scope": {
    "domain": "finance | chatbot | banking",
    "action_class": "TRADE_EXECUTION | CHATBOT_EXECUTION | LOAN_EXECUTION",
    "allowed_topics": ["VOLATILITY_ESCALATION", "RISK_THRESHOLD_POLICY"],
    "allowed_corpora": ["INTERNAL_RISK_RUNBOOKS"],
    "allowed_doc_types": ["PDF", "POLICY_TEXT", "MARKDOWN"],
    "temporal_scope": "LAST_365_DAYS",
    "max_results": 10,
    "citation_policy": "CITE_REQUIRED"
  }
}
```

### J14 — HPVD_RetrievalRaw (output Stage 13)

```json
{
  "schema_id": "manithy.hpvd.retrieval_raw.v2",
  "binding": "NON_BINDING",
  "query_id": "Q_TRADE_EXECUTION_SUPPORT",
  "candidates": [
    {
      "doc_id": "hist_case_4421",
      "chunk_id": "c01",
      "calibrated_similarity": 0.84,
      "confidence_interval": [0.78, 0.89],
      "phase_label": "EXECUTION_PHASE",
      "abstention_flag": false
    }
  ],
  "lineage": {
    "knowledge_snapshot": "ksnap_finance_2026_02_01",
    "retrieval_config_id": "hpvd_cfg_finance_v1"
  }
}
```

### J15 — PhaseFilteredSet (output Stage 14)

```json
{
  "schema_id": "manithy.hpvd.phase_filtered.v1",
  "binding": "NON_BINDING",
  "accepted": [
    {"doc_id": "hist_case_4421", "chunk_id": "c01", "calibrated_similarity": 0.84}
  ],
  "rejected": [
    {"doc_id": "hist_case_0099", "reason": "PHASE_MISMATCH"}
  ]
}
```

### J16 — AnalogFamilyAssignment (output Stage 15)

```json
{
  "schema_id": "manithy.hpvd.analog_family.v1",
  "binding": "NON_BINDING",
  "family_id": "AF_HIGH_VOL_ESCALATION_V2",
  "membership_probability": 0.68,
  "confidence_interval": [0.60, 0.75],
  "cluster_snapshot_id": "cluster_finance_v2",
  "family_characteristics": {
    "dominant_pattern": "HIGH_VOLATILITY_ESCALATION",
    "historical_outcome_distribution": {
      "PERMIT": 0.21,
      "REQUIRE_OVERRIDE": 0.63,
      "BLOCK": 0.16
    }
  }
}
```

---

## 5. VectorState Format (J06)

VectorState adalah representasi vektor lengkap dari satu kasus. Terdiri dari 6 bagian:

### 5.1 Metadata (kernel identity)

```yaml
meta:
  vector_schema_version: "v2"
  ruleset_version: "r1"
  policy_bundle_version: "p1"
  commit_id: "sha256_..."
  tenant_id: "FINANCE_DESK | MERCHANT_EU | BANKING_CORE"
  action_class: "TRADE_EXECUTION | CHATBOT_EXECUTION | LOAN_EXECUTION"
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
  action_kind: "TRADE_EXECUTION | REFUND | LOAN_SUBMISSION"
  subject_key: "TRADER_005 | ORDER_67250 | APPLICATION_8891"
  irreversible: true
```

### 5.4 Domain State (berbeda per domain)

**Finance:**
```yaml
domain_state:
  p0.metrics: {rv_short, rv_long, vol_ratio, vol_of_vol, amihud_illiquidity}
  p0.flags:   {proc_fail}
  p1.metrics: {K, LCV, LTV, entropy_density}
  p1.flags:   {K_EXCESS, LCV_SPIKE, LTV_SHOCK, IDD, POPPER_FALSIFIABLE}
  availability: {liquidity_proxy_known, volatility_structure_known, curvature_signal_known}
```

**Chatbot/Refund:**
```yaml
domain_state:
  p0.metrics: {amount_minor}
  p0.flags:   {customer_present, operator_initiated}
  availability: {original_payment_state_known, psp_refund_capability_known, chargeback_state_known}
```

**Banking/Loan:**
```yaml
domain_state:
  p0.metrics: {requested_amount_minor, income_minor, debt_ratio}
  p0.flags:   {collateral_present}
  p1.metrics: {credit_signal_entropy}
  availability: {income_verified, bureau_data_known, collateral_valuation_known}
```

### 5.5 Structural State

```yaml
structural_state:
  trajectory_length_bucket: ENUM
  commit_density_bucket: ENUM
  authority_stability_flag: boolean
  entropy_bucket: ENUM
```

---

## 6. KL Integration

### 6.1 Peran Knowledge Layer

KL berperan di **Stage 12–13** pipeline Manithy:
- **Stage 12:** KL menyediakan snapshot pengetahuan yang immutable dan version-pinned
- **Stage 13:** KL menjadi sumber *candidate pool* untuk HPVD retrieval

**KL Base URL:** `https://knowledge-layer-production.up.railway.app`

### 6.2 KL API Saat Ini

| Endpoint | Deskripsi |
|----------|-----------|
| `POST /events` | Buat event dengan hash chain |
| `GET /events?tenant_id=` | List events per tenant |
| `POST /documents` | Buat document metadata |
| `GET /documents?tenant_id=` | List documents per tenant |
| `POST /documents/{id}/versions` | Upload versi baru (file) |
| `GET /documents/{id}/versions` | List versi document |

### 6.3 Gap Analysis

| # | Gap | Severity | Status | Dampak ke HPVD |
|:-:|-----|:--------:|--------|----------------|
| G1 | Snapshot Pinning / Pinset Management | 🔴 Critical | Belum ada | HPVD tidak bisa resolve `pinset_snapshot_id` |
| G2 | Chunk-level Storage & Retrieval | 🔴 Critical | Belum ada | HPVD tidak bisa retrieval granular per chunk |
| G3 | Metadata terstruktur (domain, action_class, phase_label) | 🟠 High | Parsial | Filtering candidate pool tidak bisa dilakukan |
| G4 | Ontology & Calibration Versioning | 🟠 High | Belum ada | HPVD tidak bisa resolve versi kalibrasi |
| G5 | Content Retrieval (file download) | 🟠 High | Belum ada | HPVD tidak bisa membaca isi dokumen |
| G6 | Search / Query Endpoint dengan filter | 🟡 Medium | Belum ada | Harus fetch semua dokumen, filter di client |
| G7 | Temporal Scope Filtering | 🟡 Medium | Belum ada | `LAST_365_DAYS` scope tidak bisa diaplikasikan |

**Prioritas implementasi KL:**
1. **Fase 1:** G5 (download content) + G3 (metadata) — minimum viable integration
2. **Fase 2:** G1 (snapshot pinning) + G6 (search endpoint)
3. **Fase 3:** G2 (chunk-level) + G4 (ontology/calibration) + G7 (temporal)

### 6.4 Target Integration Flow (setelah semua gap terpenuhi)

```
HPVD menerima J13 (PostCoreQuery)
│
│  J13.opaque_pack_ref.pinset_snapshot_id = "PINSET_2026W10"
│
├─► [1] GET /snapshots/PINSET_2026W10
│       → document list + version + ontology_version + calibration_version
│
├─► [2] POST /documents/search
│       { tenant_id, filters: {action_class, phase_label, domain},
│         snapshot_id, temporal_scope, limit: 50 }
│       → candidate documents yang sudah difilter
│
├─► [3] GET /documents/{id}/versions/{v}/chunks
│       → chunks dari setiap candidate document
│
├─► [4] HPVD melakukan:
│       - Structural/semantic similarity computation
│       - Confidence interval calculation
│       - Abstention evaluation
│
└─► [5] Output: J14 (HPVD_RetrievalRaw)
        { candidates: [...], lineage: {knowledge_snapshot, retrieval_config_id} }
```

---

*Last updated: 2026-04-01 | Matrix22 / Kalibry Finance*
