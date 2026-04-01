# Changelog & Roadmap

---

## v1.0.0-alpha1 — Current

**Released:** January 2026

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

## Roadmap

### Phase 1 — Real Data: EODHD Integration

Replace synthetic data dengan real market trajectories dari [eodhd.com](https://eodhd.com).

Key tasks: EODHD data loader → trajectory builder → feature engineering (R45) → regime labeler → DNA constructor → validate T1–T8 on real data → index 10K trajectories.

**Success criteria:** `search_families()` returns meaningful analog families on real AAPL/MSFT/GOOGL within <50ms.

### Phase 2 — Qdrant Migration

Move dari in-memory FAISS ke persistent Qdrant untuk production readiness.

Key tasks: `QdrantTrajectoryIndex` adapter → collection schema design → incremental indexing → benchmark vs FAISS at 10K/50K/100K.

**Success criteria:** Qdrant-backed `HPVDEngine` passes all 72 tests. Query latency <100ms at 100K.

### Phase 3 — PMR-DB Handoff

Connect HPVD output ke Probabilistic Model Registry Database.

Key tasks: `PmrAdapter` → family merging → entropy computation → abstention gating → end-to-end test.

**Success criteria:** PMR-DB receives `hpvd_output_v1` JSON dan returns calibrated probability distributions.

### Phase 4 — Production API

Expose HPVD+PMR as REST API.

Key tasks: FastAPI `POST /search` → authentication → rate limiting → Docker packaging → Prometheus metrics.

**Success criteria:** API returns analog families in <1s under concurrent load, 99.9% uptime.

### Phase 5 — Scale & Advanced Features

PQ/OPQ compressed embeddings → cross-encoder reranking → distributed sharding (10M+) → topological features → multi-asset classes.

---

## Test History

| Date | Tests | Notes |
|------|-------|-------|
| 2026-01-15 | 29 passed | Early suite: synthetic scenarios (7) + sparse index (10) + trajectory (12) |
| 2026-03-14 | 72 passed | Full suite: added contract (30) + embedding (7) + adapters + KL integration |

> `docs/synthetic_test_results.md` (Jan 2026) deprecated dan digantikan oleh test suite 72 tests saat ini.
