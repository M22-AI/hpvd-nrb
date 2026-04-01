# HPVD Core — Technical Reference

> **HPVD (Hybrid Probabilistic Vector Database)** adalah retrieval engine domain-agnostik yang mencari analog historis dan mengelompokkannya menjadi *Analog Families* dengan uncertainty flags. HPVD adalah komponen **structural similarity** — bukan predictor. Semua output bersifat *candidates-only*; downstream system (PMR-DB) yang bertanggung jawab atas probabilitas.

**Version:** 1.0.0-alpha1 | **Project:** Matrix22 / Kalibry Finance

---

## Daftar Isi

1. [System Context](#1-system-context)
2. [Data Model](#2-data-model)
3. [Index Architecture](#3-index-architecture)
4. [Distance & Similarity](#4-distance--similarity)
5. [Search Pipeline](#5-search-pipeline)
6. [Quality Gates & Test Scenarios](#6-quality-gates--test-scenarios)
7. [Configuration Reference](#7-configuration-reference)
8. [API Reference](#8-api-reference)

---

## 1. System Context

```
OHLCV Data
    │
    ▼
Embedding Engine (OHLCV → R45 features → 60×45 matrix → 256-d PCA)
    │
    ▼
┌───────────────────────────────────────┐
│              HPVD                     │
│  Sparse Filter → Dense Search →       │
│  Hybrid Reranking → Family Formation  │
└───────────────────────────────────────┘
    │
    ▼  hpvd_output_v1 (outcome-blind)
PMR-DB  (probabilistic aggregation, abstention)
    │
    ▼
REST API / LLM Render
```

**Key specifications:**

| Parameter | MVP Target | Production Target |
|-----------|-----------|-------------------|
| Trajectory dimension | 60 × 45 (2,700 features) | Same |
| Reduced embedding | 256-d (PCA) | 128–256-d |
| Query latency | < 50ms | < 20ms |
| Database scale | 100K trajectories | 10M+ trajectories |
| Recall@K | > 85% | > 90% |

---

## 2. Data Model

### 2.1 Trajectory: 60 × 45 Matrix

Setiap trajectory merepresentasikan **60 hari trading × 45 engineered features (R45)**:

| Block | Features | Count | Deskripsi |
|-------|----------|-------|-----------|
| A | Returns | 8 | 1d/5d/10d/20d returns (plain & log) |
| B | Trend | 10 | Slopes, R², MA crossovers |
| C | Volatility | 12 | Realized vol, ATR, shocks, gaps |
| D | Price Structure | 10 | Candle patterns, skew, kurtosis |
| E | Regime | 5 | Trend/vol/momentum/structure regimes |
| **Total** | | **45** | |

### 2.2 Regime Encoding

Regime adalah **3-tuple `(trend, volatility, structural)`** dengan nilai `{-1, 0, +1}`:

| Regime | Tuple | Description |
|--------|-------|-------------|
| R1 | `(1, 0, 1)` | Stable expansion |
| R2 | `(-1, 0, -1)` | Stable contraction |
| R3 | `(0, 1, 1)` | Compression / crowding |
| R4 | `(0, 0, 0)` | Transitional / ambiguous |
| R5 | `(1, 1, -1)` | Structural stress |
| R6 | — | Novel / unseen |

27 kombinasi regime tersedia (`3³`). Sparse index meng-cover semua kombinasi dalam O(1).

### 2.3 HPVDInputBundle — Outcome-Blind Contract

`HPVDInputBundle` adalah input container resmi. Field-field berikut **TIDAK BOLEH** ada di dalam bundle:

- `label_h1`, `label_h5` — outcome labels
- `return_h1`, `return_h5` — actual returns
- Apapun yang merupakan *future information*

Validasi dilakukan via `HPVDInputBundle.validate()`. Pelanggaran diblokir.

**Bundle JSON format:**
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

## 3. Index Architecture

### 3.1 Sparse Regime Index

`SparseRegimeIndex` — inverted index berbasis regime tuple untuk pre-filtering O(1).

| Operation | Complexity | Keterangan |
|-----------|-----------|------------|
| `add()` | O(1) | Insert ke 3 index sekaligus |
| `filter_by_regime()` | O(27) = O(1) | Hanya 27 kombinasi regime |
| `combined_filter()` | O(F × K) | F = jumlah filter aktif |
| `get_regime_match_score()` | O(1) | Per-dimension scoring |

**Memory:** ~230 bytes per trajectory → 23 MB untuk 100K trajectories.

Adjacent regime matching (`allow_adjacent=True`): match `±1` per dimensi — contoh, query R1 `(1,0,1)` juga match `(1,0,0)`, `(0,0,1)`, `(1,1,1)`, dll.

### 3.2 Dense Index (FAISS)

`DenseTrajectoryIndex` — FAISS wrapper dengan cosine similarity pada 256-d PCA embeddings.

| Scale | Index Type | Latency | Recall |
|-------|-----------|---------|--------|
| < 100K | `IndexFlatIP` | < 5ms | 100% |
| 100K – 1M | `IndexIVFFlat` | < 10ms | ~95% |
| 1M – 10M | `IndexHNSW` | < 15ms | ~92% |
| > 10M | `IndexHNSW + PQ` | < 20ms | ~90% |

**MVP:** `IndexIVFFlat` (approximate, ~95% recall, < 10ms pada 100K).

### 3.3 Cognitive DNA (16-d)

DNA adalah **phase identity vector 16-dimensi** yang merepresentasikan evolusi temporal trajectory. Similarity dihitung sebagai kombinasi cosine + L2 + phase proximity, lalu di-fuse ke dalam distance akhir.

---

## 4. Distance & Similarity

### 4.1 Hybrid Distance Formula

```
Component Distances:
  d_euc  = ||vec(A) - vec(B)||₂
  d_cos  = 1 - cos(vec(A), vec(B))
  d_temp = Σᵢ wᵢ ||Aᵢ - Bᵢ||₂    (wᵢ = 0.95^(59-i) / Σⱼ 0.95^(59-j))

Normalization:
  d̂_euc  = d_euc  / (√2700 × 2)
  d̂_cos  = d_cos  / 2
  d̂_temp = d_temp / (√45 × 2)

Regime Match Score:
  regime_match = mean([1 - |Rₐᵢ - Rᵦᵢ| / 2  for i in 0,1,2])

Combined:
  base        = 0.3 × d̂_euc + 0.4 × d̂_cos + 0.3 × d̂_temp
  penalty     = (1 - regime_match) × 0.2
  hybrid_dist = base × (1 + penalty)

Fusion with DNA:
  fused_dist  = 0.7 × hybrid_dist + 0.3 × dna_distance
  confidence  = max(0, 1 - min(fused_dist, 1))
```

### 4.2 Analog Cohesion Index (ACI)

```
ACI = 1 - (mean(distances) + std(distances)) / 2
```

- ACI tinggi → analog saling mirip → hasil lebih reliable
- Target: ACI > 0.7 untuk 80% query

### 4.3 Abstention Rule

```
entropy = -p × log₂(p) - (1-p) × log₂(1-p)
if entropy > 0.9 → abstain (sinyal ke PMR-DB: "LOW_CONFIDENCE")
```

---

## 5. Search Pipeline

```
Query (HPVDInputBundle)
    │
    ▼  Stage 1: Sparse Filtering           ~2ms
    │  regime_index.filter(allow_adjacent=True)
    │  → 30K–50K candidate IDs
    │
    ▼  Stage 2: Dense Retrieval (FAISS)    ~15ms
    │  dense_index.search_with_filter(k=75)
    │  → 75 ranked candidates
    │
    ▼  Stage 3: Hybrid Reranking           ~5ms
    │  distance_calc.compute() per candidate
    │  sort by fused_dist, take top-K
    │
    ▼  Stage 4: Family Formation           ~2ms
    │  group by regime → Analog Families
    │  compute coherence + uncertainty flags
    │
HPVD_Output (hpvd_output_v1)              total ~24ms
```

### Fallback logic

Jika sparse filter menghasilkan terlalu sedikit kandidat:
1. Relax ke trend-only filter
2. Relax ke no filter (semua trajectories)

### Output Schema

```json
{
  "metadata": {
    "hpvd_version": "v1",
    "query_id": "...",
    "schema_version": "hpvd_output_v1",
    "timestamp": "2024-01-15T00:00:00+00:00"
  },
  "retrieval_diagnostics": {
    "candidates_considered": 200,
    "candidates_retrieved": 100,
    "candidates_admitted": 45,
    "families_formed": 3,
    "latency_ms": 12.5
  },
  "analog_families": [
    {
      "family_id": "AF_001",
      "members": [
        {"trajectory_id": "hist_034", "confidence": 0.57}
      ],
      "coherence": {"mean_confidence": 0.55, "dispersion": 0.03, "size": 15},
      "structural_signature": {
        "phase": "stable_expansion",
        "avg_K": 5.2,
        "avg_LTV": 0.3
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

---

## 6. Quality Gates & Test Scenarios

### 6.1 Synthetic Test Scenarios (T1–T8)

| Test | Scenario | Yang Divalidasi |
|------|----------|----------------|
| T1 | Clean Repetition | Same regime (R1) → 1 dominant family, high coherence |
| T2 | Surface Similarity Trap | R1 vs R3 similar at endpoint → NOT merged |
| T3 | Scale Invariance | Same phase, different amplitude → still grouped |
| T4 | Transitional Ambiguity | R4 between R1 and R5 → ≥2 families, uncertainty flagged |
| T5 | Novel Structure | Unseen R6 → no families OR all `weak_support=True` |
| T6 | Deterministic Replay | Same query twice → bitwise identical output |
| T7 | Overlapping Regimes | Mixed R1/R3/R5 pool → no crash, valid structure |
| T8 | Noise Stress | R1 with escalating noise → confidence decays gradually |

### 6.2 Quality Metrics Targets

| Metric | Target | Source |
|--------|--------|--------|
| ACI | > 0.7 untuk 80% query | Sprint Plan |
| Regime Coherence (RC) | > 0.65 | Sprint Plan |
| ECE (calibration) | < 8% | Sprint Plan |
| Brier Score | < 0.18 | Sprint Plan |
| Query latency P95 | < 50ms | Architecture spec |
| Abstention trigger | entropy > 0.9 | Sprint Plan |

### 6.3 Test Coverage (72 tests)

| File | Tests | Coverage |
|------|-------|---------|
| `test_contract.py` | 30 | Bundle validation, embedding lifecycle guard, serializer round-trip |
| `test_synthetic_scenarios.py` | 10 | T1–T8 epistemic scenarios |
| `test_embedding.py` | 7 | PCA fit/transform, save/load, determinism |
| `test_sparse_index.py` | 10 | Add/remove/filter, regime match scoring |
| `test_trajectory.py` | 13 | Trajectory creation, validation, DNA handling |
| `test_adapters.py` + `test_kl_integration.py` | 2 | Pipeline adapter, KL integration |

---

## 7. Configuration Reference

### Default Parameters

| Parameter | Default | Keterangan |
|-----------|---------|------------|
| `default_k` | 25 | Jumlah neighbors |
| `search_k_multiplier` | 3 | Oversample sebelum reranking |
| `min_candidates` | 100 | Minimum sparse filter results |
| `weight_euclidean` | 0.3 | Euclidean weight |
| `weight_cosine` | 0.4 | Cosine weight |
| `weight_temporal` | 0.3 | Temporal weight |
| `regime_penalty` | 0.2 | Regime mismatch penalty |
| `temporal_decay` | 0.95 | Decay factor untuk temporal weights |
| `embedding_dim` | 256 | PCA output dimension |
| `trajectory_window` | 60 | Hari per trajectory |
| `feature_count` | 45 | R45 features |
| `min_aci` | 0.7 | Minimum ACI threshold |
| `abstention_entropy` | 0.9 | Entropy abstention threshold |

### Environment Variables

```bash
HPVD_DEFAULT_K=25
HPVD_SEARCH_MULTIPLIER=3
HPVD_MIN_CANDIDATES=100
HPVD_WEIGHT_EUCLIDEAN=0.3
HPVD_WEIGHT_COSINE=0.4
HPVD_WEIGHT_TEMPORAL=0.3
HPVD_REGIME_PENALTY=0.2
HPVD_INDEX_TYPE=ivf_flat       # flat_ip | ivf_flat | hnsw
HPVD_MIN_ACI=0.5
```

---

## 8. API Reference

### Python API

```python
from hpvd import HPVDEngine, HPVDInputBundle, HPVD_Output

# Build index
engine = HPVDEngine()
engine.build_from_bundles(list_of_bundles)   # List[HPVDInputBundle]

# Search
output: HPVD_Output = engine.search_families(query_bundle)

# Serialize
d = output.to_dict()             # → dict
j = output.to_json(indent=2)     # → JSON string

# Deserialize
restored = HPVD_Output.from_dict(d)
```

### Multi-Domain Pipeline API (J13 → J16)

```python
from hpvd.adapters import HPVDPipelineEngine
from hpvd.adapters.strategies import FinanceRetrievalStrategy, DocumentRetrievalStrategy

pipeline = HPVDPipelineEngine()
pipeline.register_strategy(FinanceRetrievalStrategy(config))
pipeline.register_strategy(DocumentRetrievalStrategy())

# Build indexes per domain
pipeline.build_finance_index(trajectory_bundles)
pipeline.build_document_index(document_chunks)

# Process J13 — strategy auto-selected by domain
output = pipeline.process_query(j13_dict)
# output.j14, output.j15, output.j16
```

### CLI

```powershell
# Build index dari folder berisi HPVDInputBundle JSON files
python -m src.hpvd.cli build-index --bundles data/bundles/ --output artifacts/

# Search (dari file atau stdin)
python -m src.hpvd.cli search --index artifacts/ --query query_bundle.json
cat query_bundle.json | python -m src.hpvd.cli search --index artifacts/
```

### Legacy API (Deprecated)

```python
engine.build(trajectories)          # → gunakan build_from_bundles()
engine.search(trajectory)           # → gunakan search_families()
engine.search_families(trajectory)  # → gunakan HPVDInputBundle, bukan Trajectory
```

Semua legacy method masih berfungsi tapi emit `DeprecationWarning`.

---

*Version 1.0.0-alpha1 | Matrix22 / Kalibry Finance*
