# Knowledge Layer — Gap Analysis

> Dokumen ini menjelaskan **gap** antara fitur Knowledge Layer (KL) yang saat ini tersedia dengan kebutuhan **HPVD (Hybrid Probabilistic Vector Database)** berdasarkan [End-to-End Design](./End_to_End_Design.md), khususnya Stage 12 (Knowledge Snapshot Pin) dan Stage 13 (HPVD Retrieval).
>
> **Tujuan:** Menjadi acuan bagi tim KL untuk memahami apa yang dibutuhkan HPVD dan melengkapi fitur-fitur yang belum tersedia.

---

## Daftar Isi

1. [Konteks: Peran KL dalam Pipeline Manithy](#1-konteks-peran-kl-dalam-pipeline-manithy)
2. [Fitur KL Saat Ini](#2-fitur-kl-saat-ini)
3. [Kebutuhan HPVD dari KL](#3-kebutuhan-hpvd-dari-kl)
4. [Daftar Gap](#4-daftar-gap)
5. [Detail Gap & Rekomendasi](#5-detail-gap--rekomendasi)
6. [Prioritas Implementasi](#6-prioritas-implementasi)
7. [Contoh Alur Integrasi (Target)](#7-contoh-alur-integrasi-target)

---

## 1. Konteks: Peran KL dalam Pipeline Manithy

Dalam pipeline Manithy (18 stage), KL berperan di **Stage 12–13**:

```
Core Pipeline (Stage 1–10)
        │
        ▼
[Stage 11] Serving Adapter ──► J13 (PostCoreQuery)
        │
        ▼
[Stage 12] Knowledge Snapshot Pin ──► KL menyediakan snapshot pengetahuan yang di-pin
        │
        ▼
[Stage 13] HPVD Retrieval ──► HPVD mencari analog historis dari data yang disediakan KL
        │
        ▼
[Stage 14–18] Phase Filter → Analog Family → PMR → Reasoning → LLM Render
```

**Yang HPVD butuhkan dari KL:**
1. Koleksi kasus historis yang bisa di-retrieve berdasarkan kesamaan struktural
2. Snapshot pengetahuan yang **immutable** dan **version-pinned**
3. Metadata yang cukup untuk filtering (tenant, domain, phase, action_class)

---

## 2. Fitur KL Saat Ini

**Base URL:** `https://knowledge-layer-production.up.railway.app`

### 2.1 Events

| Endpoint | Deskripsi |
|----------|-----------|
| `POST /events` | Buat event (dengan hash chain) |
| `GET /events?tenant_id=` | List events per tenant |
| `GET /events/{event_id}` | Baca satu event |
| `GET /events/chain/verify` | Verifikasi integritas hash chain |

**Schema EventCreate:**
- `tenant_id` (required), `event_kind` (required), `commit_id` (optional), `payload` (required, free-form JSON), `created_by` (optional)

**Schema EventRead** (response):
- Semua field di atas + `previous_hash`, `event_hash`, `created_at`

### 2.2 Documents

| Endpoint | Deskripsi |
|----------|-----------|
| `POST /documents` | Buat document metadata |
| `GET /documents?tenant_id=` | List documents per tenant |
| `GET /documents/{document_id}` | Baca satu document |
| `POST /documents/{document_id}/versions` | Upload versi baru (file) |
| `GET /documents/{document_id}/versions` | List semua versi document |

**Schema DocumentCreate:**
- `tenant_id` (required), `title` (required), `document_type` (optional), `created_by` (optional)

**Schema DocumentVersionRead** (response):
- `version_number`, `file_path`, `file_size`, `checksum_sha256`, `uploaded_by`, `created_at`

---

## 3. Kebutuhan HPVD dari KL

Berdasarkan End-to-End Design, HPVD membutuhkan data berikut dari KL:

### 3.1 Saat Knowledge Snapshot Pin (Stage 12)

HPVD menerima `J13.PostCoreQuery` yang berisi `pinset_snapshot_id`. Dari KL, HPVD perlu me-resolve:

| Data | Deskripsi | Contoh |
|------|-----------|--------|
| `dataset_snapshot_id` | Snapshot dataset historis yang digunakan | `snap_finance_2026W10` |
| `ontology_version` | Versi ontologi yang berlaku | `ontology_finance_v2` |
| `calibration_model_version` | Versi model kalibrasi similarity | `calib_v3` |

### 3.2 Saat HPVD Retrieval (Stage 13)

HPVD perlu melakukan **structural-first analog retrieval** terhadap dataset historis:

| Kebutuhan | Deskripsi |
|-----------|-----------|
| **Candidate Pool** | Koleksi kasus historis yang bisa dicari berdasarkan action_class, phase_label, tenant |
| **Vector Data** | Data vektor dari kasus historis (VectorState / J06 historis) untuk similarity computation |
| **Chunk-level Access** | Akses per-chunk dari dokumen untuk retrieval granular |
| **Metadata Filtering** | Filter berdasarkan: `action_class`, `phase_label`, `tenant_id`, temporal scope |
| **Similarity Search** | Search berdasarkan vector similarity (bukan hanya keyword) |

### 3.3 Output yang HPVD Hasilkan (J14)

Untuk referensi, ini output J14 yang HPVD harus produce — tergantung data dari KL:

```json
{
  "candidates": [
    {
      "doc_id": "...",
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

---

## 4. Daftar Gap

| # | Gap | Severity | Status KL Saat Ini | Dampak ke HPVD |
|:-:|-----|:--------:|-------------------|-----------------|
| G1 | **Snapshot Pinning / Pinset Management** | 🔴 Critical | Tidak ada endpoint khusus | HPVD tidak bisa me-resolve `pinset_snapshot_id` ke set dokumen/versi yang tepat |
| G2 | **Chunk-level Storage & Retrieval** | 🔴 Critical | Tidak ada — hanya file-level | HPVD tidak bisa melakukan retrieval granular per chunk |
| G3 | **Metadata pada Dokumen/Chunk** | 🟠 High | `document_type` saja (string) | HPVD perlu filter berdasarkan `action_class`, `phase_label`, `tenant_id`, `domain` |
| G4 | **Ontology & Calibration Versioning** | 🟠 High | Tidak ada | HPVD perlu tahu versi ontologi dan model kalibrasi saat retrieval |
| G5 | **Content Retrieval (File Download)** | 🟠 High | Belum ada endpoint download konten file | HPVD tidak bisa membaca isi dokumen yang sudah di-upload |
| G6 | **Search / Query Endpoint** | 🟡 Medium | Hanya list dengan pagination | HPVD harus fetch semua dokumen lalu filter sendiri — tidak efisien |
| G7 | **Temporal Scope Filtering** | 🟡 Medium | Tidak ada filter waktu | `PostCoreQuery.scope.temporal_scope` (e.g. `LAST_365_DAYS`) tidak bisa diaplikasikan di KL |

---

## 5. Detail Gap & Rekomendasi

### G1 — Snapshot Pinning / Pinset Management 🔴

**Masalah:**
HPVD menerima `pinset_snapshot_id` dari J13 dan perlu me-resolve ke **set dokumen + versi spesifik** yang immutable. Saat ini KL tidak punya konsep "snapshot" yang membundle beberapa dokumen pada versi tertentu.

**Yang dibutuhkan:**

```
POST /snapshots
{
  "tenant_id": "FINANCE_DESK",
  "snapshot_id": "PINSET_2026W10",          // ID yang bisa di-resolve dari J13
  "description": "Weekly knowledge pin for finance",
  "items": [
    {
      "document_id": "uuid-1",
      "version_number": 3                    // Versi spesifik yang di-pin
    },
    {
      "document_id": "uuid-2",
      "version_number": 1
    }
  ],
  "ontology_version": "ontology_finance_v2",
  "calibration_model_version": "calib_v3",
  "created_by": "system"
}
```

```
GET /snapshots/{snapshot_id}
→ Mengembalikan seluruh items (document + version) yang termasuk dalam snapshot tersebut.
```

**Constraint penting:**
- Snapshot harus **immutable** — setelah dibuat, tidak bisa diubah
- Snapshot harus menyimpan `checksum_sha256` dari setiap dokumen versi yang di-pin
- HPVD akan memvalidasi integrity terhadap checksum ini

---

### G2 — Chunk-level Storage & Retrieval 🔴

**Masalah:**
HPVD melakukan retrieval pada level **chunk**, bukan pada level dokumen utuh. Saat ini KL hanya menyimpan file secara keseluruhan.

HPVD output (J14) merujuk ke `chunk_id` (e.g. `"chunk_id": "c01"`), yang berarti KL perlu mendukung chunking.

**Yang dibutuhkan:**

```
POST /documents/{document_id}/versions/{version_number}/chunks
[
  {
    "chunk_id": "c01",
    "content": "Teks chunk pertama...",
    "sequence": 1,
    "metadata": {
      "action_class": "TRADE_EXECUTION",
      "phase_label": "EXECUTION_PHASE",
      "domain": "finance"
    }
  },
  {
    "chunk_id": "c02",
    "content": "Teks chunk kedua...",
    "sequence": 2,
    "metadata": { ... }
  }
]
```

```
GET /documents/{document_id}/versions/{version_number}/chunks
→ List semua chunks dari versi dokumen tertentu.
```

```
GET /documents/{document_id}/versions/{version_number}/chunks/{chunk_id}
→ Baca satu chunk.
```

**Catatan:**
- Proses chunking bisa dilakukan di sisi KL (saat upload) atau di sisi consumer (HPVD). Tim perlu sepakat. Jika di sisi KL, perlu strategi chunking yang konsisten.
- Setiap chunk perlu `checksum` sendiri agar bisa di-verify oleh HPVD.

---

### G3 — Metadata pada Dokumen / Chunk 🟠

**Masalah:**
Saat ini `DocumentCreate` hanya punya `document_type` (string) sebagai satu-satunya metadata. HPVD membutuhkan metadata yang lebih terstruktur untuk filtering saat retrieval.

**Yang dibutuhkan di level dokumen:**

```json
{
  "tenant_id": "FINANCE_DESK",
  "title": "High Volatility Trade Case #4421",
  "document_type": "HISTORICAL_CASE",
  "metadata": {
    "domain": "finance",
    "action_class": "TRADE_EXECUTION",
    "phase_label": "EXECUTION_PHASE",
    "tags": ["high_volatility", "escalation"],
    "event_date": "2025-11-15"
  }
}
```

**Metadata fields yang HPVD perlukan (minimal):**

| Field | Type | Deskripsi | Digunakan untuk |
|-------|------|-----------|-----------------|
| `domain` | enum: `finance`, `chatbot`, `banking` | Domain kasus | Filter candidate pool |
| `action_class` | string | Tipe aksi (e.g. `TRADE_EXECUTION`) | Structural matching |
| `phase_label` | string | Fase lifecycle (e.g. `EXECUTION_PHASE`) | Phase consistency filter (Stage 14) |
| `tags` | string[] | Label pattern (e.g. `high_volatility`) | Analog family classification |
| `event_date` | date | Tanggal kasus | Temporal scope filtering |

---

### G4 — Ontology & Calibration Versioning 🟠

**Masalah:**
HPVD di Stage 12 perlu me-resolve `ontology_version` dan `calibration_model_version` dari snapshot. KL belum punya konsep ini.

**Rekomendasi:**
Bisa dimasukkan sebagai bagian dari **Snapshot** (lihat G1) atau sebagai resource terpisah:

```
GET /ontologies?tenant_id=FINANCE_DESK&version=v2
GET /calibrations?tenant_id=FINANCE_DESK&version=v3
```

Atau cukup sebagai **metadata di dalam Snapshot** (pendekatan lebih sederhana):

```json
// Di dalam response GET /snapshots/{snapshot_id}
{
  "snapshot_id": "PINSET_2026W10",
  "ontology_version": "ontology_finance_v2",
  "calibration_model_version": "calib_v3",
  ...
}
```

---

### G5 — Content Retrieval (File Download) 🟠

**Masalah:**
KL menyediakan upload file via `POST /documents/{id}/versions`, dan response mengembalikan `file_path`. Tapi **tidak ada endpoint untuk download / membaca konten file**. HPVD tidak bisa mengambil isi dokumen.

**Yang dibutuhkan:**

```
GET /documents/{document_id}/versions/{version_number}/content
→ Mengembalikan konten file dokumen (binary/text).
```

Atau jika chunk-level sudah diimplementasi (G2), ini mungkin bisa di-cover via chunk retrieval.

---

### G6 — Search / Query Endpoint 🟡

**Masalah:**
HPVD perlu mencari dokumen berdasarkan metadata (action_class, phase_label, domain, temporal scope). Saat ini hanya tersedia `GET /documents?tenant_id=` dengan `limit` dan `offset`.

**Yang dibutuhkan:**

```
GET /documents/search?tenant_id=FINANCE_DESK&domain=finance&action_class=TRADE_EXECUTION&phase_label=EXECUTION_PHASE&from_date=2025-03-10&to_date=2026-03-10&limit=50
```

Atau via POST jika query kompleks:

```
POST /documents/search
{
  "tenant_id": "FINANCE_DESK",
  "filters": {
    "domain": "finance",
    "action_class": "TRADE_EXECUTION",
    "phase_label": "EXECUTION_PHASE"
  },
  "temporal_scope": {
    "from": "2025-03-10",
    "to": "2026-03-10"
  },
  "limit": 50,
  "offset": 0
}
```

---

### G7 — Temporal Scope Filtering 🟡

**Masalah:**
`PostCoreQuery` (J13) menyertakan `temporal_scope` (e.g. `LAST_365_DAYS`). KL tidak mendukung filter berdasarkan waktu.

**Yang dibutuhkan:**
Bisa diimplementasikan sebagai bagian dari Search (G6) dengan parameter `from_date` / `to_date`, atau sebagai filter tersendiri di list endpoints.

---

## 6. Prioritas Implementasi

Urutan yang disarankan agar HPVD bisa mulai integrasi secepat mungkin:

| Fase | Gap | Alasan |
|:----:|-----|--------|
| **Fase 1** | G5 (Content Retrieval) | Tanpa ini, HPVD tidak bisa membaca dokumen sama sekali |
| **Fase 1** | G3 (Metadata) | Minimum agar HPVD bisa filter candidate pool |
| **Fase 2** | G1 (Snapshot Pinning) | Agar HPVD bisa me-resolve `pinset_snapshot_id` — kunci immutability |
| **Fase 2** | G6 (Search) | Agar retrieval efisien, tidak perlu fetch semua lalu filter di client |
| **Fase 3** | G2 (Chunk-level) | Untuk retrieval granular — bisa diimplementasikan setelah dasar berjalan |
| **Fase 3** | G4 (Ontology/Calibration) | Bisa workaround via Snapshot metadata dulu |
| **Fase 3** | G7 (Temporal Filtering) | Bisa workaround via Search filter |

---

## 7. Contoh Alur Integrasi (Target)

Berikut alur ideal setelah semua gap terpenuhi:

```
HPVD menerima J13 (PostCoreQuery)
│
│  J13.opaque_pack_ref.pinset_snapshot_id = "PINSET_2026W10"
│
├─► [1] GET /snapshots/PINSET_2026W10
│       → Dapat list document_id + version_number + ontology_version + calibration_version
│
├─► [2] GET /documents/search
│       {
│         "tenant_id": "FINANCE_DESK",
│         "filters": { "action_class": "TRADE_EXECUTION", "phase_label": "EXECUTION_PHASE" },
│         "snapshot_id": "PINSET_2026W10",
│         "temporal_scope": { "from": "2025-03-10", "to": "2026-03-10" },
│         "limit": 50
│       }
│       → Dapat candidate documents yang sudah difilter
│
├─► [3] GET /documents/{id}/versions/{v}/chunks
│       → Dapat chunks dari setiap candidate document
│
├─► [4] HPVD melakukan:
│       - Structural similarity computation (calibrated_similarity)
│       - Confidence interval calculation
│       - Abstention evaluation
│
└─► [5] Output: J14 (HPVD_RetrievalRaw)
        {
          "candidates": [...],
          "lineage": {
            "knowledge_snapshot": "PINSET_2026W10",
            "retrieval_config_id": "hpvd_cfg_finance_v1"
          }
        }
```

---

## Referensi

- [End-to-End Design](./End_to_End_Design.md) — Stage 12 (Knowledge Snapshot Pin), Stage 13 (HPVD Retrieval)
- [KL API Docs](https://knowledge-layer-production.up.railway.app/docs#/) — Swagger UI
- [KL OpenAPI Spec](https://knowledge-layer-production.up.railway.app/openapi.json)

---

> **Last updated:** 2026-03-10
