# HPVD Adaptation Strategy: Trajectory vs Document Retrieval

> Dokumen ini menjelaskan bagaimana HPVD disesuaikan untuk mendukung design Manithy yang mencakup tiga domain: **Finance** (trajectory), **Chatbot/Refund** (dokumen), dan **Banking/Loan** (dokumen OCR).

---

## Daftar Isi

1. [Masalah Inti: Trajectory ≠ Document](#1-masalah-inti-trajectory--document)
2. [Apa yang Diminta End-to-End Design](#2-apa-yang-diminta-end-to-end-design)
3. [Solusi Arsitektur: Domain-Specific Retrieval Strategy](#3-solusi-arsitektur-domain-specific-retrieval-strategy)
4. [Concept Mapping: Finance → Document](#4-concept-mapping-finance--document)
5. [Komponen yang Perlu Dibangun](#5-komponen-yang-perlu-dibangun)
   - [5.1 Retrieval Strategy Interface](#51-retrieval-strategy-interface)
   - [5.2 Finance Strategy (HPVD Core Wrapper)](#52-finance-strategy-hpvd-core-wrapper)
   - [5.3 Document Strategy (Semantic Vector Search)](#53-document-strategy-semantic-vector-search)
   - [5.4 Strategy Dispatcher](#54-strategy-dispatcher)
   - [5.5 J-File Adapter Layer](#55-j-file-adapter-layer)
   - [5.6 Pipeline Engine](#56-pipeline-engine)
6. [Struktur File Baru](#6-struktur-file-baru)
7. [Rencana Implementasi](#7-rencana-implementasi)
8. [Yang Tidak Perlu Diubah](#8-yang-tidak-perlu-diubah)

---

## 1. Masalah Inti: Trajectory ≠ Document

HPVD saat ini didesain untuk **financial trajectory** — data deret waktu 60×45 (60 hari × 45 fitur) yang memiliki urutan temporal bermakna. Namun end-to-end design membutuhkan retrieval untuk **dokumen teks** (chatbot/refund policies, loan/OCR documents) yang **tidak memiliki urutan temporal**.

| Aspek | Financial Trajectory | Document (Chatbot/Banking) |
|-------|---------------------|---------------------------|
| **Struktur** | 60×45 matrix, fixed shape | Teks panjang variabel, tabel, paragraf |
| **Urutan** | Temporal — hari ke-1 → hari ke-60 **bermakna** | Paragraf ke-1 → ke-5 **tidak selalu bermakna** |
| **Regime** | (trend, volatility, structural) = {-1, 0, +1} | Tidak ada "regime" alami |
| **DNA** | 16-d phase identity (evolusi temporal) | Tidak ada "phase evolution" |
| **Distance** | Temporal decay masuk akal (hari terbaru lebih penting) | Temporal decay **tidak masuk akal** |
| **Family** | Grup trajectory yang berevolusi serupa | Grup dokumen yang... ? |

### Kesimpulan

Dokumen **tidak bisa** diproses langsung oleh HPVD core (trajectory engine). Tapi end-to-end design **tidak meminta itu** — yang diminta adalah **unified retrieval layer** dengan output contract yang sama.

---

## 2. Apa yang Diminta End-to-End Design

Dari sheet **tech flow**, stage 13–15 (HPVD):

```
Input:  J13_PostCoreQuery  →  scope, allowed_topics, corpora
Output: J14_HPVD_RetrievalRaw  →  candidates + calibrated_similarity
        J15_PhaseFilteredSet    →  accepted / rejected per phase filter
        J16_AnalogFamilyAssignment → family + membership_probability
```

**Key insight**: HPVD di end-to-end design bukan satu engine monolitik — ia adalah **retrieval layer** yang harus bisa dispatch ke **strategy berbeda** tergantung domain.

Contoh J13 untuk Chatbot:

```json
{
  "schema_id": "manithy.post_core_query.v2",
  "binding": "NON_BINDING",
  "query_id": "Q_REFUND_SUPPORT_MATERIAL",
  "scope": {
    "domain": "chatbot",
    "action_class": "CHATBOT_EXECUTION"
  },
  "allowed_topics": ["REFUND_PROCESS", "PSP_RULES", "CHARGEBACK_INTERACTION"],
  "allowed_corpora": ["INTERNAL_RUNBOOKS", "PSP_CONTRACTS"],
  "allowed_doc_types": ["PDF", "MARKDOWN", "POLICY_TEXT"]
}
```

Contoh J13 untuk Finance:

```json
{
  "schema_id": "manithy.post_core_query.v2",
  "query_id": "Q_TRADE_EXECUTION_SUPPORT",
  "scope": {
    "domain": "finance",
    "action_class": "TRADE_EXECUTION"
  },
  "allowed_topics": ["VOLATILITY_ESCALATION", "RISK_THRESHOLD_POLICY"],
  "allowed_corpora": ["INTERNAL_RISK_RUNBOOKS", "MARKET_RISK_POLICY"]
}
```

Meskipun J13 berbeda per domain, **output contract J14/J15/J16 identik** — inilah yang memungkinkan PMR-DB downstream tidak perlu tahu retrieval strategy mana yang dipakai.

---

## 3. Solusi Arsitektur: Domain-Specific Retrieval Strategy

```
┌─────────────────────────────────────────────────────┐
│                   HPVDPipelineEngine                  │
│                  (unified J13 → J14/J15/J16)          │
├──────────┬──────────────────┬────────────────────────┤
│          │     Strategy     │                        │
│          │    Dispatcher    │                        │
│          └────────┬─────────┘                        │
│    ┌──────────────┼──────────────┐                   │
│    ▼              ▼              ▼                   │
│ ┌────────┐  ┌──────────┐  ┌──────────┐             │
│ │Finance │  │ Document │  │ Banking  │             │
│ │Strategy│  │ Strategy │  │ Strategy │             │
│ │        │  │          │  │          │             │
│ │HPVD    │  │Semantic  │  │Hybrid    │             │
│ │Core    │  │Vector    │  │OCR+Vec   │             │
│ │(60×45) │  │Search    │  │Search    │             │
│ └────────┘  └──────────┘  └──────────┘             │
│    ▼              ▼              ▼                   │
│    J14            J14            J14    ← same       │
│    J15            J15            J15    ← output     │
│    J16            J16            J16    ← contract   │
└─────────────────────────────────────────────────────┘
```

### Prinsip

- **Input contract sama** (J13)
- **Output contract sama** (J14/J15/J16)
- **Retrieval strategy berbeda** per domain
- HPVD Core (trajectory) tetap dipakai untuk **Finance** saja
- Domain lain pakai **strategy yang sesuai** (semantic embedding untuk dokumen)
- **Outcome-blind principle tetap berlaku** di semua strategy

---

## 4. Concept Mapping: Finance → Document

Ini adalah peta mental untuk memahami bagaimana konsep HPVD diterjemahkan ke domain dokumen:

```
┌──────────────────────────────────────────────────────────────────────┐
│                    CONCEPT MAPPING                                    │
│                                                                       │
│   FINANCE (Trajectory)          DOCUMENT (Chatbot/Banking)           │
│   ═══════════════════          ═══════════════════════════           │
│                                                                       │
│   60×45 matrix                 → Text chunk (variable length)         │
│   PCA → 256-d embedding        → Sentence-transformer → 384-d embed │
│                                                                       │
│   Regime tuple (trend,vol,str) → Topic category (categorical)        │
│   SparseRegimeIndex (O(1))     → Topic inverted index (O(1))         │
│                                                                       │
│   DNA 16-d (phase identity)    → Doc-type signature (categorical)    │
│   DNA similarity (continuous)  → Doc-type match (binary/hierarchical)│
│                                                                       │
│   Temporal distance            → NOT APPLICABLE ❌                    │
│   (recent days weighted more)    (paragraphs have no "recent end")   │
│                                                                       │
│   Euclidean + Cosine + Temporal → Cosine similarity ONLY             │
│   (multi-component hybrid)       (single component is sufficient)    │
│                                                                       │
│   Family (regime coherence)    → Cluster (semantic topic coherence)  │
│   Family uncertainty flags     → Same: weak_support, high_dispersion │
│                                                                       │
│   calibrated_similarity        → calibrated_similarity               │
│   = structural compatibility    = semantic compatibility             │
│   ≠ outcome probability         ≠ outcome probability               │
│   (outcome-blind PRESERVED)     (outcome-blind PRESERVED ✅)         │
└──────────────────────────────────────────────────────────────────────┘
```

### Detail Mapping per Komponen

#### Embedding

| Finance | Document |
|---------|----------|
| Input: 60×45 matrix = 2700 float | Input: Teks string, panjang variabel |
| Method: PCA on flattened vector | Method: Sentence-transformer encoding |
| Output: 256-d dense vector | Output: 384-d dense vector |
| Training: Fit PCA on historical set | Training: Pre-trained model (all-MiniLM-L6-v2) |

#### Sparse Filter (Pre-filtering)

| Finance | Document |
|---------|----------|
| Key: Regime tuple `(trend, vol, structural)` | Key: Topic category string |
| Lookup: Inverted index by tuple | Lookup: Inverted index by topic |
| Purpose: O(1) elimination of regime mismatches | Purpose: O(1) elimination of irrelevant topics |
| Example: `(1, 0, 1)` = stable expansion | Example: `"REFUND_PROCESS"` = refund-related docs |

#### Dense Search

| Finance | Document |
|---------|----------|
| Index: FAISS IVFFlat on 256-d PCA embeddings | Index: FAISS IndexFlatIP on 384-d sentence embeddings |
| Distance: Multi-component hybrid (Euclidean + Cosine + Temporal) | Distance: Cosine similarity only |
| Weights: `0.3×Euc + 0.4×Cos + 0.3×Temp` | Weights: `1.0×Cosine` (temporal tidak relevan) |

#### Phase / DNA Matching

| Finance | Document |
|---------|----------|
| DNA: 16-d continuous vector (phase identity) | Doc-type: Categorical string (e.g. "policy.refund") |
| Comparison: Cosine + Euclidean + Phase proximity | Comparison: Exact match or hierarchical prefix match |
| Weight: `dna_similarity_weight = 0.3` | Weight: Binary boost or penalty |

#### Family Formation

| Finance | Document |
|---------|----------|
| Grouping: Regime-based coherence | Grouping: Topic-based semantic clustering |
| Coherence: Mean confidence within regime group | Coherence: Mean similarity within topic cluster |
| Uncertainty flags: `weak_support`, `high_dispersion`, `boundary_case` | Same flags, same semantics |

---

## 5. Komponen yang Perlu Dibangun

### 5.1 Retrieval Strategy Interface

Abstract base class yang mendefinisikan contract untuk semua domain strategy:

```python
class RetrievalStrategy(ABC):
    """Base class for domain-specific retrieval strategies."""

    @property
    @abstractmethod
    def domain(self) -> str:
        """Domain name: 'finance', 'document', etc."""
        ...

    @abstractmethod
    def build_index(self, corpus: list) -> None:
        """
        Build retrieval index from domain-specific corpus.
        - Finance: list of HPVDInputBundle
        - Document: list of DocumentChunk (text)
        """
        ...

    @abstractmethod
    def search(self, query: Dict, k: int = 25) -> RetrievalResult:
        """Perform retrieval, return candidates."""
        ...

    @abstractmethod
    def compute_families(self, candidates: list) -> list:
        """Group candidates into analog families."""
        ...
```

**Output**: `RetrievalResult` — berisi `List[RetrievalCandidate]` yang domain-agnostic.

### 5.2 Finance Strategy (HPVD Core Wrapper)

Membungkus `HPVDEngine` yang sudah ada sebagai salah satu strategy:

```python
class FinanceRetrievalStrategy(RetrievalStrategy):
    """Wraps existing HPVD core for trajectory search."""

    def __init__(self, config: HPVDConfig):
        self._engine = HPVDEngine(config)

    @property
    def domain(self) -> str:
        return "finance"

    def build_index(self, corpus):
        self._engine.build_from_bundles(corpus)

    def search(self, query, k=25):
        # J13 → HPVDInputBundle via J13Adapter
        # HPVDEngine.search_families()
        # Convert internal results → RetrievalResult
        ...
```

**HPVD core tidak diubah** — hanya dibungkus.

### 5.3 Document Strategy (Semantic Vector Search)

Strategy baru untuk domain chatbot dan banking:

```python
class DocumentRetrievalStrategy(RetrievalStrategy):
    """Semantic embedding search for text documents."""

    def __init__(self, embedding_model="all-MiniLM-L6-v2"):
        self._model = None  # lazy loaded
        self._faiss_index = None
        self._topic_index = {}  # equivalent to SparseRegimeIndex

    @property
    def domain(self) -> str:
        return "document"

    def build_index(self, corpus):
        # 1. Compute sentence embeddings (384-d)
        # 2. Build FAISS IndexFlatIP (cosine on normalized vectors)
        # 3. Build topic inverted index
        ...

    def search(self, query, k=25):
        # 1. Embed query text → 384-d
        # 2. Topic pre-filter (like sparse regime filter)
        # 3. FAISS cosine search (like dense trajectory search)
        # 4. Doc-type match (like DNA similarity)
        # 5. Return RetrievalResult (same format as finance)
        ...

    def compute_families(self, candidates):
        # Group by topic (like grouping by regime)
        # Compute coherence within each topic group
        # Return AnalogFamily objects (same structure)
        ...
```

#### Arsitektur Document Strategy

```
┌──────────────────────────────────────────────────────┐
│  Document Strategy                                    │
│                                                       │
│  Query text                                           │
│    → Sentence embedding (384-d)                       │
│    → Topic filter (categorical, like regime filter)   │
│    → FAISS cosine search (flat or IVF)                │
│    → Doc-type matching (categorical, like DNA)        │
│    → Semantic clustering (like family formation)      │
│    → RetrievalResult (same output contract)           │
└──────────────────────────────────────────────────────┘
```

#### Document Chunk Data Model

```python
@dataclass
class DocumentChunk:
    chunk_id: str           # unique identifier
    text: str               # actual text content
    topic: str = ""         # equivalent to "regime" (categorical)
    doc_type: str = ""      # equivalent to "DNA phase" (document identity)
    metadata: Dict = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None  # pre-computed or will be computed
```

### 5.4 Strategy Dispatcher

Routes J13 queries ke strategy yang benar berdasarkan domain:

```python
class StrategyDispatcher:
    """Maps domain → retrieval strategy."""

    DOMAIN_ALIASES = {
        "finance": "finance",
        "equity": "finance",
        "chatbot": "document",
        "refund": "document",
        "banking": "document",
        "loan": "document",
    }

    def register(self, strategy: RetrievalStrategy) -> None:
        """Register a strategy for its domain."""
        ...

    def dispatch(self, j13_dict: Dict) -> RetrievalStrategy:
        """Determine strategy from J13 scope.domain."""
        ...
```

### 5.5 J-File Adapter Layer

Adapter antara J-file format pipeline dan HPVD internal format:

| Adapter | Fungsi |
|---------|--------|
| **J13Adapter** | `J13_PostCoreQuery` → `HPVDInputBundle` (finance) atau query dict (document) |
| **J14Emitter** | Raw candidates → `J14_HPVD_RetrievalRaw` |
| **J15Emitter** | Phase-filtered candidates → `J15_PhaseFilteredSet` |
| **J16Emitter** | Family assignment → `J16_AnalogFamilyAssignment` |
| **VectorStateReader** | Extract domain context dari VectorState snapshot |

### 5.6 Pipeline Engine

Wrapper yang menyatukan semua komponen:

```python
class HPVDPipelineEngine:
    """
    Unified pipeline: J13 in → J14+J15+J16 out.
    
    Usage:
        pipeline = HPVDPipelineEngine()
        pipeline.register_strategy(FinanceRetrievalStrategy(config))
        pipeline.register_strategy(DocumentRetrievalStrategy())
        
        # Build indexes per domain
        pipeline.build_finance_index(trajectory_bundles)
        pipeline.build_document_index(document_chunks)
        
        # Process any J13 — strategy auto-selected
        output = pipeline.process_query(j13_dict)
        # output.j14, output.j15, output.j16 → send to PMR-DB
    """
```

---

## 6. Struktur File Baru

```
src/hpvd/
├── __init__.py
├── engine.py                          # Core HPVDEngine (UNCHANGED)
├── trajectory.py                      # Core data model (UNCHANGED)
├── sparse_index.py                    # Regime index (UNCHANGED)
├── dense_index.py                     # FAISS wrapper (UNCHANGED)
├── distance.py                        # Hybrid distance (UNCHANGED)
├── dna_similarity.py                  # DNA matching (UNCHANGED)
├── family.py                          # Family formation (UNCHANGED)
├── embedding.py                       # PCA embedding (UNCHANGED)
├── synthetic_data_generator.py        # Test data (UNCHANGED)
│
├── adapters/                          # 🆕 Pipeline integration layer
│   ├── __init__.py
│   ├── retrieval_strategy.py          # Abstract base + common types
│   ├── strategy_dispatcher.py         # Domain → strategy routing
│   ├── j13_adapter.py                 # J13 → internal query format
│   ├── j14_emitter.py                 # Raw candidates → J14 output
│   ├── j15_emitter.py                 # Phase filtered → J15 output
│   ├── j16_emitter.py                 # Family assignment → J16 output
│   ├── vectorstate_reader.py          # VectorState context extraction
│   ├── pipeline_engine.py             # Full pipeline wrapper
│   │
│   └── strategies/                    # 🆕 Domain-specific strategies
│       ├── __init__.py
│       ├── finance_strategy.py        # Wraps existing HPVDEngine
│       └── document_strategy.py       # Semantic vector search for docs
```

---

## 7. Rencana Implementasi

### Minggu 1 (Prioritas Tinggi)

| # | Task | Est. |
|---|------|------|
| 1 | `RetrievalStrategy` interface + `RetrievalCandidate` common types | 1 hari |
| 2 | `FinanceRetrievalStrategy` (wrap HPVD core) | 1 hari |
| 3 | `J13Adapter` + `VectorStateReader` | 1 hari |
| 4 | `J16Emitter` (critical path ke PMR-DB) | 0.5 hari |
| 5 | `HPVDPipelineEngine` + `StrategyDispatcher` | 1 hari |
| 6 | End-to-end test: J13 Finance → J14/J15/J16 | 0.5 hari |

### Minggu 2 (Document Support + Polish)

| # | Task | Est. |
|---|------|------|
| 7 | `DocumentRetrievalStrategy` (sentence-transformers + FAISS) | 3 hari |
| 8 | `J14Emitter` + `J15Emitter` (diagnostics) | 1 hari |
| 9 | Integration test: J13 Chatbot → J14/J15/J16 | 1 hari |
| 10 | Integration test dengan data dari KL (Arfiano) | 1 hari |

### Dependencies

```
KL (Arfiano) → consumed data → HPVD adapters
                                      ↓
                                  J16 output → PMR-DB (Fitria)
                                      ↓
                                  J17/J18 → Serving
```

---

## 8. Yang Tidak Perlu Diubah

| Komponen | Status | Alasan |
|----------|--------|--------|
| `HPVDEngine` | ✅ Tidak diubah | Core trajectory engine tetap valid untuk finance |
| `Trajectory` / `HPVDInputBundle` | ✅ Tidak diubah | Data model finance tetap |
| `SparseRegimeIndex` | ✅ Tidak diubah | Dipakai oleh finance strategy |
| `DenseTrajectoryIndex` | ✅ Tidak diubah | Dipakai oleh finance strategy |
| `HybridDistanceCalculator` | ✅ Tidak diubah | Dipakai oleh finance strategy |
| `DNASimilarityCalculator` | ✅ Tidak diubah | Dipakai oleh finance strategy |
| `FamilyFormationEngine` | ✅ Tidak diubah | Dipakai oleh finance strategy, re-used konsepnya oleh document strategy |
| `EmbeddingComputer` | ✅ Tidak diubah | PCA untuk finance tetap |
| Outcome-blind principle | ✅ Berlaku di semua domain | `calibrated_similarity` = structural/semantic compatibility, bukan outcome probability |
| Existing tests (T1–T8) | ✅ Tetap pass | HPVD core tidak berubah |

---

## Appendix: Mengapa Bukan Satu Engine untuk Semua?

Alternatif yang **ditolak**: "Ubah HPVD core agar bisa menerima dokumen juga".

**Alasan penolakan:**

1. **Forced shape**: Memaksakan dokumen ke 60×45 matrix akan menghilangkan informasi semantik dan menambahkan noise
2. **Temporal decay**: Memberi bobot lebih tinggi pada "paragraf terakhir" dokumen tidak masuk akal
3. **Regime concept**: Dokumen tidak memiliki `(trend, volatility, structural)` regime — memaksakan ini menghasilkan meaningless categories
4. **DNA vector**: Phase identity 16-d didesain untuk evolusi temporal — dokumen tidak berevolusi
5. **Performance**: Sentence-transformer embeddings jauh lebih efektif untuk text similarity daripada PCA pada matrix 60×45
6. **Separation of concerns**: Satu engine yang mencoba melakukan segalanya akan sulit di-maintain dan di-test

Pendekatan **strategy pattern** mempertahankan kekuatan masing-masing domain sambil menyediakan interface pipeline yang seragam.
