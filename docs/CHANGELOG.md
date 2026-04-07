# Changelog & Roadmap

---

## v1.0.0-alpha3 — HPVD REST API + KL Integration — Current

**Released:** April 2026

### Capabilities Delivered (alpha3)

| Capability | Status | Details |
|-----------|--------|---------|
| FastAPI REST API layer | ✅ | `POST /query` (J13 → PipelineOutput), `GET /health` |
| KLCorpusLoader | ✅ | Load corpus dari KL REST API saat startup (httpx sync, 6-step flow) |
| object_type inference | ✅ | Infer dari isi dokumen: `policy_id` / `product_id` / `mapping_id` / `doc_type` |
| `.env` support | ✅ | `KL_API_KEY`, `KL_BASE_URL`, `KL_DOMAIN` via python-dotenv |
| httpx HTTP client | ✅ | Sync HTTP client untuk semua KL API calls |

### Known Limitations (alpha3)

- Corpus reload hanya saat startup (tidak ada hot reload)
- Tidak ada auth untuk endpoint HPVD (internal NRB use only)
- `object_type` di-infer dari content, bukan dari KL `document_type` metadata
- Hanya support satu domain/sector per instance

---

## v1.0.0-alpha2 — Manithy v1 Architecture Pivot

**Released:** April 2026

### Architectural Pivot: Kalibry Finance → Manithy v1

Project ini mengalami architectural pivot dari "Kalibry Finance / Trajectory Intelligence" ke **Manithy v1 — Deterministic Attestation System**. Perubahan utama:

| Dimensi | Sebelum (alpha1) | Sesudah (alpha2) |
|---------|-----------------|-----------------|
| Identity | Kalibry Finance / Matrix22 | Manithy v1 |
| Peran HPVD | Cari analog historis (60×45 matrix) | Retrieve Knowledge (Policy/Product/RuleMapping) |
| Posisi HPVD | Post-Core (triggered by J13 dari Core) | NRB (sebelum Core, sesudah Parser) |
| Primary input | `HPVDInputBundle` (trajectory + DNA) | `observed_data + metadata.sector` dari Parser |
| Primary output | `hpvd_output_v1` (analog families) | `candidates [{type, data, provenance}]` |
| Domain scope | Finance-only (OHLCV) | Sector-agnostic (Banking/Finance/Chatbot) |

### Capabilities Delivered (alpha2)

| Capability | Status | Details |
|-----------|--------|---------|
| KnowledgeRetrievalStrategy | ✅ | Sector filter + field-based matching + mandatory rule_mapping |
| Knowledge schemas | ✅ | `PolicyObject`, `ProductObject`, `RuleMappingObject`, `DocumentSchema`, `KnowledgeCandidate` |
| HPVDPipelineEngine.build_knowledge_index() | ✅ | Convenience builder for Knowledge Layer corpus |
| J13 Manithy v1 fields | ✅ | `observed_data` + `sector` fields added (backward compatible) |
| Domain alias: `"knowledge"` | ✅ | New domain in `StrategyDispatcher` |
| 13 new knowledge retrieval tests | ✅ | K1–K7 scenarios + schema unit tests |
| docs/HPVD_CORE.md rewrite | ✅ | Primary interface = Knowledge objects. Finance = secondary subsection. |
| docs/MANITHY_INTEGRATION.md update | ✅ | HPVD in NRB, new pipeline diagram, updated J-files reference |
| .cursor/rules/hpvd_specs.mdc update | ✅ | J-file position, legacy finance boundary, KnowledgeCandidate contract |

### Known Limitations (alpha2)

- `KnowledgeRetrievalStrategy` uses in-memory storage (no persistent Knowledge Layer API yet)
- Field-based matching is keyword-level only (no semantic/vector similarity yet)
- `NRBOrchestrator` not yet implemented (HPVD called directly via HPVDPipelineEngine)
- `PMR` and `KnowledgeBuilder` not yet implemented (NRB pipeline incomplete)
- No Qdrant integration (FAISS in-memory only)
- No REST/gRPC API
- No real sector data (all testing uses synthetic/fixture data)

---

## v1.0.0-alpha1 — Finance Engine (Legacy)

**Released:** January–March 2026

### Capabilities Delivered (MVP)

| Capability | Status | Details |
|-----------|--------|---------|
| Sparse regime filtering | ✅ | O(1) inverted index, 27 regime combinations |
| Dense FAISS search | ✅ | IVFFlat/Flat with 256-d PCA embeddings |
| Multi-channel fusion | ✅ | Trajectory distance + DNA similarity (configurable weights) |
| Analog Family formation | ✅ | Regime-grouped families with coherence + uncertainty |
| Outcome-blind contract | ✅ | `HPVDInputBundle.validate()` rejects outcome fields |
| Embedding lifecycle guard | ✅ | `RuntimeError` if PCA not fitted before transform |
| Serializer `hpvd_output_v1` | ✅ | `to_dict()` / `to_json()` / `from_dict()` round-trip |
| CLI entrypoint | ✅ | `build-index` dan `search` subcommands |
| Deprecation on legacy API | ✅ | `build()`, `search()`, `Trajectory` input warned |
| 72 automated tests | ✅ | Contract, scenarios T1–T8, embedding, sparse, trajectory |
| Multi-domain adapter layer | ✅ | `HPVDPipelineEngine` + `FinanceStrategy` + `DocumentStrategy` |
| KL integration (v2) | ✅ | `KLClient`, `KLDocumentLoader`, pipeline demo |

**Performance (synthetic, single machine):**
- Build time: ~0.5s for 500 trajectories
- Search latency: ~10–15ms per query
- Target: <50ms at 100K trajectories

### Known Limitations (Not Yet Implemented)

- No Qdrant integration (FAISS in-memory only, save/load via pickle)
- No REST/gRPC API (CLI and Python API only)
- No PMR-DB integration (boundary defined, not built)
- No real market data pipeline (all testing uses synthetic data)
- No cross-encoder reranking
- No distributed sharding
- No monitoring/observability

---

## Roadmap (Manithy v1)

### Phase 0 — Knowledge Layer Starter (CURRENT)

Build dan validate Knowledge Layer retrieval dengan fixture data (Policy/Product/RuleMapping JSON files per sektor).

Key tasks (done): `KnowledgeRetrievalStrategy` → `KnowledgeIndex` → sector filter + field match → mandatory rule_mapping → 13 new tests passing.

**Success criteria (done):** `KnowledgeRetrievalStrategy` retrieves correct candidates for Banking/Finance/Chatbot sectors. 147 tests passing.

### Phase 1 — NRB Orchestrator + Parser

Implement NRB pipeline: `NRBOrchestrator` → `ParserRegistry` → `ParserBanking` / `ParserChatbot` → HPVD → PMR → `KnowledgeBuilder`.

Key tasks: `NRBOrchestrator.run_nrb(request)` → Parser per sektor → HPVD → PMR (hypothesis builder) → KnowledgeBuilder (KNOWN/UNKNOWN/CONFLICT).

**Success criteria:** Full NRB pipeline dari raw request → epistemic state (KNOWN/UNKNOWN/CONFLICT).

### Phase 2 — Knowledge Layer REST API

Move dari in-memory JSON files ke persistent Knowledge Layer dengan REST API.

Key tasks: REST endpoint `GET /knowledge?sector=banking&type=policy` → versioning → snapshot pinning.

**Success criteria:** `KnowledgeRetrievalStrategy` retrieves from REST API, tidak dari in-memory. Query latency <50ms.

### Phase 3 — Core Integration (t-1 Boundary)

Connect NRB output (epistemic state) ke Core layer melalui boundary t-1.

Key tasks: `Producer t-1` → freeze observed_state → `Adapter (CCR)` → `VectorState (J06)` → `V1` (Coverage) → `V3` (Decision) → `Evidence Pack`.

**Success criteria:** End-to-end test: raw request → Parser → HPVD → PMR → KnowledgeBuilder → Core → Evidence Pack.

### Phase 4 — Production API & Replay

Expose Manithy system sebagai REST API dengan deterministic replay capability.

Key tasks: FastAPI → authentication → `ReplayReport` → Docker packaging.

### Phase 5 — Finance Market Data (Legacy Path)

Jika Finance market data (OHLCV) tetap dibutuhkan: Real data pipeline dengan EODHD → Qdrant migration → cross-encoder reranking.

Key tasks: EODHD data loader → trajectory builder → R45 features → `QdrantTrajectoryIndex`.

**Success criteria:** `FinanceRetrievalStrategy` returns meaningful analog families on real AAPL/MSFT/GOOGL within <50ms.

---

## Test History

| Date | Tests | Notes |
|------|-------|-------|
| 2026-01-15 | 29 passed | Early suite: synthetic scenarios (7) + sparse index (10) + trajectory (12) |
| 2026-03-14 | 72 passed | Full suite: added contract (30) + embedding (7) + adapters + KL integration |
| 2026-04-01 | 147 passed | Architecture pivot: added 13 knowledge retrieval tests (K1–K7 + schema). 72 legacy tests preserved. |

> `docs/synthetic_test_results.md` (Jan 2026) deprecated dan digantikan oleh test suite saat ini.
