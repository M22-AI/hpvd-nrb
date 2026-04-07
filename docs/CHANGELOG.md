# Changelog & Roadmap

---

# # v1.0.0-alpha3 — HPVD rest API + KL Integration — Current

* *Released: * * April 2026

# # # Capabilities Delivered (alpha3)

| Capability | Status | Details |
|-----------|--------|---------|
| FastAPI rest API layer | ✅ | __ code_0__ (J13 PipelineOutput)→, __ code_1 __ |
| KLCorpusLoader | ✅ | Load corpus from KL rest API at startup (httpx sync, 6-step flow) |
| object_type inference | ✅ | Infer from the contents of the document: __ code_0 __ / __ code _1 __ / __ code _2 __ / __ code _3 __ |
| __ code_0 __ support | ✅ | __code_1 __, __ code_2 __,__ code_3 __ via python-dotenv |
| httpx HTTP client | ✅ | sync HTTP client for all KL API calls |

# # # Known Limitations (alpha3)

- Corpus reload only at startup (no hot reload)
- No auth for HPVD endpoint (internal NRB use only)
- __code_0 __ inferred from content, not from KL __ code_1__ metadata
- Only support one domain/sector per instance

---

# # v1.0.0-alpha2 — Manithy v1 Architecture Pivot

* *Released: * * April 2026

# # # Architectural Pivot: Kalibry Finance → Manithy v1

This project experienced an architectural pivot from "Kalibry Finance / Trajectory Intelligence" to * *Manithy v1 — Deterministic Attestation System* *. Key changes:

| Dimensions | Before (alpha1) | After (alpha2) |
|---------|-----------------|-----------------|
| Identity | Kalibry Finance / Matrix22 | Manithy v1 |
| Role of HPVD | Search historical analogues (60×45 matrix) | Retrieve Knowledge (Policy/Product/RuleMapping) |
| HPVD position | Post-Core (triggered by J13 from Core) | NRB (before Core, after Parser) |
| primary input | __ code_0 __ (trajectory + DNA) | __ code_1 __ from Parser |
| primary output | __ code_0 __ (analog families) | __ code_1 __ |
| Domain scope | Finance-only(OHLCV) | Sector-agnostic (Banking/Finance/Chatbot) |

# # # Capabilities Delivered (alpha2)

| Capability | Status | Details |
|-----------|--------|---------|
| KnowledgeRetrievalStrategy | ✅ | Sector filter + field-based matching + mandatory rule_map |
| Knowledge schemas | ✅ | __ code_0 __, __ code_1__, __ code_2__, __ code_3__, __ code_4 __ |
| HPVDPipelineEngine.build_knowledge_index() ✅ | | Convenience builder for Knowledge Layer corpus |
| J13 Manithy v1 fields | ✅ | __ code_0__ + __code_1 __ fields added (backward compatible) |
| Domain alias: __ code_0 __ | ✅ | New domain in __ code_1 __ |
| 13 new knowledge retrieval tests ✅ | | K1-K7scenarios + schema unit tests |
| docs/HPVD_CORE.md rewrite | ✅ | Primary interface = Knowledge objects. Finance = secondary subsection. |
| docs/MANITHY_INTEGRATION.md update ✅ | | HPVD in NRB, new pipeline diagram, updated J-files reference |
| .cursor/rules/hpvd_specs.mdc update ✅ | | J-file position, legacy finance boundary, KnowledgeCandidate contract |

# # # Known Limitations (alpha2)

- __code_0 __ uses in-memory storage (no persistent Knowledge Layer API yet)
-Field-based matching is keyword-level only (no semantic/vector similarity yet)
- __code_0 __ not yet implemented (HPVD called directly via HPVDPipelineEngine)
- __ code_0 __ and __code_1 __ not yet implemented (NRB pipeline incomplete)
- No Qdrant integration (FAISSin-memory only)
- REST No./gRPC API
- No real sector data (all testing uses synthetic/fixture data)

---

# # v1.0.0-alpha1 — Finance Engine (Legacy)

* *Released: * * January–March 2026

# # # Capabilities Delivered (MVP)

| Capability | Status | Details |
|-----------|--------|---------|
| Sparse filtering regime | ✅ | O(1) inverted index, 27 regime combinations |
| Dense FAISS search ✅ | | IVFFlat/Flat with 256-d PCA embeddings |
| Multi-channel fusion | ✅ | Trajectory distance + DNA similarity (configurable weights) |
| Analog Family formation ✅ | | Regime-groupedfamilies with coherence + uncertainty |
| Outcome-blind contract | ✅ | __ code_0 __ rejects outcome fields |
| Embedding lifecycle guard | ✅ | __ code_0 __ if PCA not fitted before transform |
| Serializer __ code_0 __ | ✅ | __code_ 1 __ / __code_ 2 __/__ code_3 __ round-trip |
| CLI entrypoint | ✅ | __ code_0__ and __ code_1 __ subcommands |
| Deprecation on legacy API | ✅ | __ code_0 __, __ code_1__, __ code_2 __ input warned |
| 72 automated tests ✅ | | Contract, scenarios T1-T8, embedding, sparse, trajectory |
| Multi-domain adapter layer | ✅ | __ code_0 __+__ code_1 __ + __ code_2__ |
| KL integration (v2) | ✅ | __ code_0__, __ code_1 __, demo pipeline |

* *Performance (synthetic, single machine): * *
-Build time: ~0.5s for 500 trajectories
-Search latency: ~10-15ms per query
- Target: <50ms at 100K trajectories

# # # Known Limitations (Not Yet Implemented)

- No Qdrant integration (FAISSin-memory only, save/load via pickle)
- No rest/gRPC API (CLI and Python API only)
- No PMR-DB integration (boundary defined, not built)
- No real market data pipeline (all testing uses synthetic data)
- No cross-encoder reranking
- No distributed sharding
- No monitoring/observability

---

# # Roadmap (Manithy v1)

# # # Phase 0 — Knowledge Layer Starter (CURRENT)

Build and validate Knowledge Layer retrieval with data fixture (Policy/Product/RuleMapping JSON files per sector).

Key tasks (done): __ code_0 __ → __code_1 __ → sector filter + field match → mandatory rule_mapping → 13 new tests passing.

* *Success criteria (done): * *__ code_0 __ retrieves correct candidates for Banking/Finance/Chatbot sectors. 147 tests passing.

# # # Phase 1 — NRB Orchestrator + Parser

Implementation NRB pipeline: __ code_0__ → __ code_1 → __ code_2__ / __ code _3 __ → HPVD → PMR → __ code_4 __.

Key tasks: __ code_0 __ → Parser per → sector → HPVD PMR (hypothesis builder) → KnowledgeBuilder (KNOWN/UNKNOWN/CONFLICT).

* *Success criteria: * * Full NRB pipeline from raw request → epistemic state (KNOWN/UNKNOWN/CONFLICT).

# # # Phase 2 — Knowledge Layer rest API

Move from in-memory JSON files to persistent Knowledge Layer with rest API.

Key tasks: rest endpoint __ code_0 __ → versioning → snapshot pinning.

* *Success criteria: * *__ code_0 __ retrieves from rest API, not from in-memory. Query latency <50ms.

# # # Phase 3 — Core Integration (t-1 Boundary)

Connect NRB output (epistemic state) to Core layer via boundary t-1.

Key tasks: __ code_0__ → freeze observed_state → __ code_1 → __ __code_2 → ____ code_3 __ (Coverage) → __code_4 __ (Decision) → __ code_5 __.

* *Success criteria: * * End-to-end test: raw request → Parser → HPVD → PMR → KnowledgeBuilder → Core → Evidence Pack.

# # # Phase 4 — Production API & Replay

Expose Manithy system as rest API with deterministic replay capability.

Key tasks: FastAPI → authentication → __ code_0 __ → Docker packaging.

# # # Phase 5 — Finance Market Data (Legacy Path)

If Finance market data (OHLCV) is still needed: Real data pipeline → with EODHD → Qdrant migration cross-encoder reranking.

Key tasks: EODHD data loader → trajectory builder → R45 features → __ code_0__.

* *Success criteria: * *__ code_0 __ returns meaningful analog families on real AAPL/MSFT/GOOGL within <50ms.

---

# # Test History

| Date | Tests | Notes |
|------|-------|-------|
| 2026-01-15| 29 passed | Early suite: synthetic scenarios (7) + sparse index (10) + trajectory (12) |
| 2026-03-14| 72 passed | Full suite: added contract (30) + embedding (7) + adapters + KL integration |
| 2026-04-01| 147 passed | Architecture pivot: added 13 knowledge retrieval tests (K1-K7 + schema). 72 legacy tests preserved. |

> __code_0 __ (Jan 2026) deprecated and replaced by the current test suite.
