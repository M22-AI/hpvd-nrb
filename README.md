# HPVD-M22

**Hybrid Probabilistic Vector Database for Trajectory Intelligence**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version: 1.0.0-alpha1](https://img.shields.io/badge/version-1.0.0--alpha1-orange.svg)](#)
[![Tests: 72 passed](https://img.shields.io/badge/tests-72%20passed-brightgreen.svg)](#running-tests)

---

## Table of Contents

- [Overview](#overview)
- [Core Architecture](#core-architecture)
- [Quick Start](#quick-start)
- [Running Tests](#running-tests)
- [Running the Demo](#running-the-demo)
- [CLI Usage](#cli-usage)
- [Output Schema (`hpvd_output_v1`)](#output-schema-hpvd_output_v1)
- [Key Concepts](#key-concepts)
- [Project Structure](#project-structure)
- [What Exists Today (MVP)](#what-exists-today-mvp)
- [What Doesn't Exist Yet](#what-doesnt-exist-yet)
- [Roadmap](#roadmap)
- [Dependencies](#dependencies)

---

## Overview

HPVD (Hybrid Probabilistic Vector Database) is a **multi-domain retrieval engine** for finding structurally or semantically similar historical analogs. Given a query (a financial trajectory *or* a text chunk), HPVD retrieves historically similar entries and groups them into **Analog Families** — coherent clusters with explicit uncertainty markers.

**Critical design principle:** HPVD is **outcome-blind**. It produces structured empirical evidence but does **not** compute probabilities, confidence intervals, or make predictions. That responsibility belongs to downstream systems (PMR-DB).

HPVD is composed of two layers:
- **Core engine** — domain-agnostic sparse + dense retrieval with family formation (`HPVDEngine`)
- **Adapter layer** — domain-specific strategy pattern that translates J-file envelopes into core queries and emits structured J-file outputs (`HPVDPipelineEngine`)

### What HPVD Does

- Accepts queries from multiple domains (finance, document, banking, etc.) via a unified J13 → J14 → J15 → J16 pipeline
- Finds historically analogous entries via sparse regime filtering (finance) or keyword/topic filtering (document) + dense FAISS search
- Fuses trajectory/semantic distance and Cognitive DNA similarity into a single coherence score
- Groups retrieved analogs into families with coherence metrics and uncertainty flags
- Outputs structured JSON (`hpvd_output_v1`) ready for downstream consumption

### What HPVD Does NOT Do

- Predict future prices, direction, or outcomes
- Compute probability distributions, entropy, or abstention decisions
- Make trading or business recommendations
- Access outcome labels (`label_h1`, `return_h5`, etc.) in its core logic

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

### Components

| Module | File | Role |
|--------|------|------|
| **Trajectory** | `trajectory.py` | Data model: 60×45 matrix + regime labels + DNA vector |
| **HPVDInputBundle** | `trajectory.py` | Outcome-blind input container (trajectory + DNA + geometry + metadata) |
| **SparseRegimeIndex** | `sparse_index.py` | Inverted index for O(1) regime-based candidate filtering |
| **DenseTrajectoryIndex** | `dense_index.py` | FAISS wrapper for 256-d approximate nearest neighbor search |
| **EmbeddingComputer** | `embedding.py` | PCA-based dimensionality reduction (60×45 → 256-d) |
| **HybridDistanceCalculator** | `distance.py` | Multi-component distance: `0.3×L2 + 0.4×Cosine + 0.3×Temporal` |
| **DNASimilarityCalculator** | `dna_similarity.py` | 16-d Cognitive DNA matching (cosine + L2 + phase proximity) |
| **FamilyFormationEngine** | `family.py` | Groups candidates into Analog Families with coherence metrics |
| **HPVDEngine** | `engine.py` | Core orchestrator combining all components |
| **HPVDPipelineEngine** | `adapters/pipeline_engine.py` | Multi-domain pipeline orchestrator (J13 → J16) |
| **RetrievalStrategy** | `adapters/retrieval_strategy.py` | Abstract base + `RetrievalCandidate` domain-agnostic output type |
| **StrategyDispatcher** | `adapters/strategy_dispatcher.py` | Routes J13 queries to the correct strategy by domain |
| **J-file schemas** | `adapters/j_file_schemas.py` | Typed dataclasses for J13/J14/J15/J16 envelopes |
| **CLI** | `cli.py` | Command-line interface (`build-index` / `search`) |

---

## Quick Start

### 1. Clone and Set Up

```powershell
cd HPVD-M22
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
# or: pip install -e ".[dev]"
```

### 2. Verify Installation

```powershell
pytest tests/ -q
# Expected: 72 passed, 32 warnings
```

### 3. Run the Demo

```powershell
python -m src.demo_hpvd
```

---

## Running Tests

```powershell
# All tests (verbose)
pytest tests/ -v

# Quick summary
pytest tests/ -q

# With coverage
pytest tests/ --cov=src/hpvd --cov-report=html
# Open htmlcov/index.html in browser

# Specific test file
pytest tests/test_contract.py -v
pytest tests/test_synthetic_scenarios.py -v
```

### Test File Overview

| File | Tests | What It Covers |
|------|-------|----------------|
| `test_contract.py` | 30 | Bundle validation, embedding lifecycle guard, deprecation warnings, round-trip schema, serializer |
| `test_synthetic_scenarios.py` | 10 | Canonical scenarios T1–T8 (clean repetition, surface similarity trap, scale invariance, transitional ambiguity, novel structure, deterministic replay, overlapping regimes, noise stress) |
| `test_embedding.py` | 7 | PCA fit/transform, save/load, determinism, variance |
| `test_sparse_index.py` | 10 | Add/remove/filter, regime match scoring, statistics |
| `test_trajectory.py` | 13 | Trajectory creation, validation, regime tuple, DNA handling, `to_hpvd_input()` |

### Synthetic Test Scenarios (T1–T8)

| Test | Scenario | What It Validates |
|------|----------|-------------------|
| T1 | Clean Repetition | Same regime (R1), small noise → 1 dominant family, high coherence |
| T2 | Surface Similarity Trap | R1 vs R3 similar at endpoint → must NOT merge them |
| T3 | Scale Invariance | Same phase at different amplitudes → still grouped |
| T4 | Transitional Ambiguity | R4 between R1 and R5 → ≥2 families, uncertainty flagged |
| T5 | Novel Structure | Unseen R6 query → no families OR all `weak_support=True` |
| T6 | Deterministic Replay | Same query twice → bitwise identical output |
| T7 | Overlapping Regimes | Mixed R1/R3/R5 pool → no crash, valid structure |
| T8 | Noise Stress | R1 with escalating noise → confidence decays gradually |

---

## Running the Demo

```powershell
# HPVD outcome-blind demo (Analog Family retrieval)
python -m src.demo_hpvd

# BM25 text retrieval prototype (separate)
python -m src.prototypes.bm25_prototype
```

The HPVD demo:
1. Generates 500 synthetic trajectories with regime profiles
2. Fits PCA embedding and builds FAISS index
3. Creates a query trajectory (R1 — stable expansion)
4. Runs multi-channel family search
5. Displays analog families with coherence metrics and uncertainty flags

---

## CLI Usage

The CLI supports two subcommands for end-to-end pipeline operation:

### Build Index

```powershell
python -m src.hpvd.cli build-index --bundles data/bundles/ --output artifacts/
```

Loads HPVDInputBundle JSON files from the specified folder, fits PCA, builds FAISS index, and saves all artifacts.

### Search

```powershell
# From file
python -m src.hpvd.cli search --index artifacts/ --query query_bundle.json

# From stdin
cat query_bundle.json | python -m src.hpvd.cli search --index artifacts/
```

Outputs `hpvd_output_v1` JSON to stdout.

### Bundle JSON Format

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

---

## Output Schema (`hpvd_output_v1`)

Every `HPVD_Output` serializes to the following JSON structure:

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
    "candidates_retrieved": 100,
    "candidates_admitted": 45,
    "candidates_rejected": 55,
    "families_formed": 3,
    "latency_ms": 12.5
  },
  "analog_families": [
    {
      "family_id": "AF_001",
      "members": [
        {"trajectory_id": "hist_034", "confidence": 0.57},
        {"trajectory_id": "hist_071", "confidence": 0.56}
      ],
      "coherence": {
        "mean_confidence": 0.55,
        "dispersion": 0.03,
        "size": 15
      },
      "structural_signature": {
        "phase": "stable_expansion",
        "avg_K": 5.2,
        "avg_LTV": 0.3,
        "avg_LVC": null
      },
      "uncertainty_flags": {
        "phase_boundary": false,
        "weak_support": false,
        "partial_overlap": false
      }
    }
  ]
}
```

### Programmatic Serialization

```python
output = engine.search_families(query_bundle)

# Serialize
d = output.to_dict()            # → dict
j = output.to_json(indent=2)    # → JSON string

# Deserialize
restored = HPVD_Output.from_dict(d)          # from dict
restored = HPVD_Output.from_dict(json.loads(j))  # from JSON
```

---

## Key Concepts

### Regime Encoding

Regimes are 3-tuples of `{-1, 0, +1}` representing `(trend, volatility, structural)`:

| Regime | Tuple | Description |
|--------|-------|-------------|
| R1 | `(1, 0, 1)` | Stable expansion |
| R2 | `(-1, 0, -1)` | Stable contraction |
| R3 | `(0, 1, 1)` | Compression / crowding |
| R4 | `(0, 0, 0)` | Transitional / ambiguous |
| R5 | `(1, 1, -1)` | Structural stress |
| R6 | — | Novel / unseen (no defined phase) |

### Distance Formula

```
hybrid_dist = (0.3 × Euclidean + 0.4 × Cosine + 0.3 × Temporal) × (1 + regime_penalty)
fused_dist  = 0.7 × hybrid_dist + 0.3 × dna_distance
confidence  = max(0, 1 - min(fused_dist, 1))
```

### Analog Families

A **family** is NOT a nearest-neighbor list. It is a coherent group with:
- **Members**: trajectory references + structural confidence scores
- **Coherence**: mean confidence, dispersion, size
- **Structural Signature**: phase name, avg curvature (K), avg LTV
- **Uncertainty Flags**: `phase_boundary`, `weak_support`, `partial_overlap`

### Outcome-Blind Contract

HPVD's frozen API surface:
- `engine.build_from_bundles(List[HPVDInputBundle])` — build index
- `engine.search_families(HPVDInputBundle)` → `HPVD_Output`

Legacy methods (`build()`, `search()`, passing `Trajectory` to `search_families`) still work but emit `DeprecationWarning`.

---

## Project Structure

```
HPVD-M22/
├── src/
│   ├── hpvd/                          # Core library
│   │   ├── __init__.py                # Public API exports
│   │   ├── trajectory.py              # Trajectory + HPVDInputBundle
│   │   ├── sparse_index.py            # Regime inverted index
│   │   ├── dense_index.py             # FAISS wrapper
│   │   ├── distance.py                # Hybrid distance calculator
│   │   ├── embedding.py               # PCA embedding computer
│   │   ├── dna_similarity.py          # Cognitive DNA matching
│   │   ├── family.py                  # Family formation engine
│   │   ├── engine.py                  # HPVDEngine + HPVD_Output
│   │   ├── cli.py                     # CLI (build-index / search)
│   │   ├── __main__.py                # python -m src.hpvd.cli
│   │   ├── synthetic_data_generator.py
│   │   └── adapters/                  # Multi-domain adapter layer
│   │       ├── j_file_schemas.py      # J13/J14/J15/J16 typed schemas
│   │       ├── j13_adapter.py         # J13 → domain query dict
│   │       ├── j14_emitter.py         # Emit J14 raw retrieval
│   │       ├── j15_emitter.py         # Emit J15 phase-filtered set
│   │       ├── j16_emitter.py         # Emit J16 family assignments
│   │       ├── pipeline_engine.py     # HPVDPipelineEngine (J13→J16)
│   │       ├── retrieval_strategy.py  # RetrievalStrategy ABC + RetrievalCandidate
│   │       └── strategy_dispatcher.py # Routes queries by domain
│   ├── demo_hpvd.py                   # End-to-end retrieval demo
│   └── prototypes/
│       └── bm25_prototype.py          # BM25 text retrieval demo
├── tests/
│   ├── conftest.py                    # Warning filters, shared fixtures
│   ├── test_contract.py               # API contract + serializer tests
│   ├── test_synthetic_scenarios.py    # T1–T8 epistemic scenarios
│   ├── test_embedding.py             # PCA embedding tests
│   ├── test_sparse_index.py          # Regime index tests
│   └── test_trajectory.py            # Data model tests
├── docs/
│   ├── HPVD_Architecture_Document.md  # System design (1180 lines)
│   ├── HPVD_Technical_Specification.md # Implementation spec (2830 lines)
│   └── synthetic_test_results.md      # Test scenario results
├── hpvd_outputs/                      # Example output files
│   ├── hpvd_output.json               # hpvd_output_v1 example
│   └── pmr_input.json                 # PMR-DB handoff example
├── synthetic_data/scenario_A/         # Pre-generated test data
├── pyproject.toml                     # Build config + pytest options
└── requirements.txt                   # Pinned dependencies
```

---

## What Exists Today (MVP)

The current `v1.0.0-alpha1` delivers single-machine retrieval:

| Capability | Status | Details |
|------------|--------|---------|
| Sparse regime filtering | ✅ | O(1) inverted index, 27 regime combinations |
| Dense FAISS search | ✅ | IVFFlat/Flat with 256-d PCA embeddings |
| Multi-channel fusion | ✅ | Trajectory distance + DNA similarity (configurable weights) |
| Analog Family formation | ✅ | Regime-grouped families with coherence + uncertainty |
| Outcome-blind contract | ✅ | `HPVDInputBundle.validate()` rejects outcome fields |
| Embedding lifecycle guard | ✅ | `RuntimeError` if PCA not fitted before transform |
| Serializer `hpvd_output_v1` | ✅ | `to_dict()` / `to_json()` / `from_dict()` round-trip |
| CLI entrypoint | ✅ | `build-index` and `search` subcommands |
| Deprecation on legacy API | ✅ | `build()`, `search()`, `Trajectory` input warned |
| 72 automated tests | ✅ | Contract, scenarios T1-T8, embedding, sparse, trajectory |
| Warning hygiene | ✅ | SWIG/FAISS warnings suppressed via `conftest.py` + `pyproject.toml` |

### Performance (synthetic, single machine)

- Build time: ~0.5s for 500 trajectories
- Search latency: ~10–15ms per query
- Target: <50ms at 100K trajectories

---

## What Doesn't Exist Yet

### 1. Qdrant Integration

The current MVP uses **FAISS** (in-memory, single-process). The timeline planned Qdrant as the production vector store but it has **not been implemented**:

- No Qdrant collection schema
- No Qdrant-based `DenseTrajectoryIndex` adapter
- No persistent vector storage (FAISS index is in-memory, save/load via pickle)
- No incremental indexing

### 2. Production API

No REST/gRPC API exists:

- No FastAPI endpoints
- No request/response schema (only CLI and Python API)
- No authentication, rate limiting, or multi-tenant support
- No deployment configuration (Docker, Kubernetes)

### 3. PMR-DB Integration

HPVD produces `HPVD_Output` but the downstream consumer is not built:

- `HPVD_Output` → PMR-DB handoff path is **defined but not implemented**
- No probability computation from analog families
- No entropy-based abstention logic
- No calibrated forecasting
- The schema contract (`hpvd_output_v1`) is finalized and ready

### 4. Real Market Data Pipeline

All current testing uses synthetic data:

- No data loader for EODHD (eodhd.com) or other market data providers
- No trajectory construction from real OHLCV time series
- No Cognitive DNA computation from real market structure
- No historical trajectory indexing (target: 100K+ trajectories)

### 5. Advanced Features

- No cross-encoder reranking for precision improvement
- No SPLADE sparse-dense hybrid (prototyped with BM25 only)
- No compressed embeddings (PQ/OPQ) for memory efficiency
- No distributed sharding for 10M+ scale
- No monitoring/observability (Prometheus, Grafana)
- No persistent homology / topological features

---

## Roadmap

### Phase 1: Data Riil — EODHD Integration *(Next)*

**Goal**: Replace synthetic data with real market trajectories from [eodhd.com](https://eodhd.com).

| Task | Description |
|------|-------------|
| EODHD data loader | Build `data_loader.py` to fetch OHLCV data via EODHD API |
| Trajectory builder | Convert raw time series → 60×45 feature matrix (price, volume, volatility, momentum, etc.) |
| Feature engineering | Define the 45 features: technical indicators, regime signals, structural metrics |
| Regime labeler | Compute `(trend, volatility, structural)` regime from real data |
| DNA constructor | Build real Cognitive DNA vectors from market structure |
| Validation | Run existing T1–T8 scenarios against real data distribution |
| Index 10K trajectories | Build initial historical database from major US equities |

**Success criteria**: `search_families()` returns meaningful analog families on real AAPL/MSFT/GOOGL trajectories within <50ms.

### Phase 2: Qdrant Migration

**Goal**: Move from in-memory FAISS to persistent Qdrant for production readiness.

| Task | Description |
|------|-------------|
| Qdrant adapter | Implement `QdrantTrajectoryIndex` as drop-in replacement for `DenseTrajectoryIndex` |
| Collection schema | Design Qdrant collection with 256-d vectors + regime payload filters |
| Incremental indexing | Support adding new trajectories without full re-index |
| Benchmark | Compare latency/recall vs FAISS at 10K, 50K, 100K scale |
| Persistence | Replace pickle-based save/load with Qdrant snapshots |

**Success criteria**: Qdrant-backed `HPVDEngine` passes all 72 existing tests. Query latency <100ms at 100K vectors.

### Phase 3: PMR-DB Handoff

**Goal**: Connect HPVD output to the Probabilistic Model Registry Database.

| Task | Description |
|------|-------------|
| PMR adapter | Build `PmrAdapter` that consumes `HPVD_Output` and produces probability distributions |
| Family merging | Implement merge logic using `compute_family_similarity()` |
| Entropy computation | Calculate information entropy from analog families |
| Abstention gating | Decide when to abstain based on family coherence / novelty |
| Integration test | End-to-end: EODHD → HPVD → PMR-DB → calibrated forecast |

**Success criteria**: PMR-DB receives `hpvd_output_v1` JSON and returns calibrated probability distributions with valid confidence intervals.

### Phase 4: Production API

**Goal**: Expose HPVD+PMR as a REST API for real-time querying.

| Task | Description |
|------|-------------|
| FastAPI server | `POST /search` accepts query bundle, returns `hpvd_output_v1` |
| Authentication | API key management |
| Rate limiting | Configurable per-client throttling |
| Docker packaging | `Dockerfile` + `docker-compose.yml` with Qdrant |
| Monitoring | Prometheus metrics + Grafana dashboard (latency, throughput, family quality) |
| Load testing | 1000 concurrent queries, P95 <2s |

**Success criteria**: API returns analog families in <1s under concurrent load with 99.9% uptime.

### Phase 5: Scale & Advanced Features

| Task | Description |
|------|-------------|
| Compressed embeddings | PQ/OPQ for 4× memory reduction |
| Cross-encoder reranking | Fine-tuned reranker for top-K precision lift |
| Distributed sharding | Support 10M+ trajectories across Qdrant shards |
| Topological features | Persistent homology for structural similarity |
| Multi-asset classes | Extend to crypto, FX, commodities, indices |

---

## Dependencies

### Core (required)

```
numpy>=1.26.0       # Array operations
pandas>=2.1.0       # Data manipulation
scipy>=1.13.0       # Scientific computing
scikit-learn>=1.4.0  # PCA, preprocessing
faiss-cpu>=1.7.4    # Vector similarity search
rank-bm25>=0.2.2    # Sparse retrieval prototype
```

### Dev (for testing/linting)

```
pytest>=7.0.0
pytest-cov>=4.0.0
black>=23.0.0
isort>=5.12.0
mypy>=1.0.0
```

### Optional ML

```
torch>=2.2.0
sentence-transformers>=2.6.0
transformers>=4.41.0
```

### Install

```powershell
pip install -r requirements.txt     # All pinned
pip install -e ".[dev]"             # Editable + dev tools
pip install -e ".[full]"            # Everything
```

---

## HPVD → PMR-DB Integration Boundary

```
HPVD (retrieval, structural)        PMR-DB (probabilistic, decisional)
─────────────────────────           ─────────────────────────────────
analog_families[]                    Probability computation
  ├── members + confidence           Confidence intervals
  ├── coherence metrics              Entropy / abstention decisions
  ├── structural_signature           Calibrated forecasts
  └── uncertainty_flags              Action recommendations
retrieval_diagnostics
metadata (schema: hpvd_output_v1)
```

**Key rule**: HPVD computes structural similarity. PMR-DB computes probabilities. The boundary is the `hpvd_output_v1` JSON contract.

---

## Documentation

- [Architecture Document](docs/HPVD_Architecture_Document.md) — System design, MVP specs (1180 lines)
- [Technical Specification](docs/HPVD_Technical_Specification.md) — Implementation details, formulas (2830 lines)
- [Synthetic Test Results](docs/synthetic_test_results.md) — T1–T8 scenario outcomes
- [12-Week Timeline](docs/Timeline.md) — Full development plan

## License

MIT License — see LICENSE file for details.

## Project: Kalibry Finance

HPVD is the retrieval component of the **Matrix22** Trajectory Intelligence system.

