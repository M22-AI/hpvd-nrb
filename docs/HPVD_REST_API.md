# HPVD REST API — Deployment & Integration Guide

> Dokumen ini ditujukan untuk **team eksternal** (Parser, NRB, PMR) yang akan memanggil HPVD sebagai REST service dalam pipeline Manithy v1. Untuk arsitektur internal HPVD, lihat [HPVD_CORE.md](HPVD_CORE.md). Untuk posisi HPVD dalam pipeline Manithy, lihat [MANITHY_INTEGRATION.md](MANITHY_INTEGRATION.md).

**Version:** 1.0.0-alpha3 | **Framework:** FastAPI + Uvicorn | **Python:** 3.10+

---

## Daftar Isi

1. [Prerequisites](#1-prerequisites)
2. [Setup & Konfigurasi](#2-setup--konfigurasi)
3. [Menjalankan Server](#3-menjalankan-server)
4. [Endpoints](#4-endpoints)
5. [Request & Response Format (Parser SDK Output)](#5-request--response-format-parser-sdk-output)
6. [Upload Knowledge Objects ke KL](#6-upload-knowledge-objects-ke-kl)
7. [Common Errors & Solusi](#7-common-errors--solusi)

---

## 1. Prerequisites

| Kebutuhan | Versi minimum | Catatan |
|-----------|--------------|---------|
| Python | 3.10 | Sudah termasuk `venv` |
| pip | terbaru | `pip install --upgrade pip` |
| Akses internet | -- | Untuk fetch corpus dari KL saat startup |
| KL API Key | -- | Format `kl_...`, minta ke tim KL |

---

## 2. Setup & Konfigurasi

### 2.1 Clone & Install

```powershell
git clone <repo-url>
cd HPVD-M22

python -m venv venv
venv\Scripts\Activate.ps1

pip install -e ".[api]"
```

> Jika `pip install -e ".[api]"` gagal, install manual:
> ```powershell
> pip install fastapi>=0.110.0 uvicorn>=0.29.0 httpx>=0.27.0 python-dotenv
> pip install -e .
> ```

### 2.2 Konfigurasi Environment

Buat file `.env` di root project (atau copy dari `.env.example`):

```env
KL_API_KEY=kl_your_key_here
KL_BASE_URL=https://knowledge-layer-production.up.railway.app
KL_DOMAIN=banking
```

| Variable | Wajib | Keterangan |
|----------|-------|-----------|
| `KL_API_KEY` | Ya | API key tenant KL (format `kl_...`) |
| `KL_BASE_URL` | Tidak | Default: `https://knowledge-layer-production.up.railway.app` |
| `KL_DOMAIN` | Tidak | Domain/sector yang di-load. Default: `banking` |

> **Penting:** File `.env` sudah ada di `.gitignore` -- jangan commit file ini.

---

## 3. Menjalankan Server

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8000 --reload
```

> **Windows:** Selalu gunakan `127.0.0.1`, bukan `0.0.0.0`, untuk akses dari browser lokal.
> `0.0.0.0` dipakai jika server harus bisa diakses dari mesin lain di jaringan (misalnya Docker atau VM).

Saat startup, HPVD akan:
1. Load `.env`
2. Fetch semua dokumen dari KL (`GET /documents?domain=banking`)
3. Parse dan infer `object_type` dari isi setiap dokumen
4. Build in-memory index
5. Log jumlah objects yang berhasil di-load

Log startup yang normal:

```
INFO:     Application startup complete.
INFO:hpvd.kl_loader:KLCorpusLoader: loaded 3 objects, skipped 1 (domain=banking)
INFO:src.hpvd.api:HPVD API ready -- 3 knowledge objects loaded (domain=banking)
```

### Verifikasi

```powershell
# Buka di browser
http://127.0.0.1:8000/health

# Atau via PowerShell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Response yang diharapkan:

```json
{"status": "ok", "corpus_size": 3, "domain": "banking"}
```

> `corpus_size: 0` berarti tidak ada dokumen yang berhasil di-load dari KL. Lihat [Section 7](#7-common-errors--solusi).

---

## 4. Endpoints

### `GET /health`

Liveness check dan status corpus.

**Response:**

```json
{
  "status": "ok",
  "corpus_size": 3,
  "domain": "banking"
}
```

| Field | Tipe | Keterangan |
|-------|------|-----------|
| `status` | string | Selalu `"ok"` jika server berjalan |
| `corpus_size` | int | Jumlah knowledge objects yang ter-load |
| `domain` | string | Domain yang aktif (dari `KL_DOMAIN`) |

---

### `POST /query`

Terima output Parser SDK, jalankan pipeline retrieval, return J14 + J15 + J16.

**Request:** `Content-Type: application/json`

Input adalah output langsung dari `banking_parser_sdk` -- lihat [Section 5](#5-request--response-format-parser-sdk-output) untuk format lengkap.

**Response:**

```json
{
  "j14": { ... },
  "j15": { ... },
  "j16": { ... }
}
```

**HTTP Status Codes:**

| Code | Kondisi |
|------|---------|
| `200` | Sukses |
| `400` | Request malformed -- `query_id` atau `sector` missing |
| `503` | Corpus kosong -- KL tidak bisa dijangkau saat startup |
| `500` | Internal error tidak terduga |

---

## 5. Request & Response Format (Parser SDK Output)

### 5.1 Posisi dalam Pipeline

```
banking_parser_sdk
  run_parser("LENDER", fields)        --> {"observed": {...}, "availability": {...}}
  run_parser("LOAN_INFORMATION", ...) --> {"observed": {...}, "availability": {...}}
  build_hpvd_query(results, sector, query_id)
                                      --> HPVDQueryRequest (kirim ke HPVD)
                                                 |
                                           POST /query
                                                 |
                                    HPVD (internal pipeline)
                                                 |
                                    {"j14": ..., "j15": ..., "j16": ...}
```

HPVD menerima format Parser SDK secara langsung. Adaptasi ke format pipeline internal dilakukan di dalam HPVD -- caller tidak perlu tahu detail implementasi internal.

### 5.2 Request Body

```json
{
  "query_id": "REQ-001",
  "sector": "banking",
  "observed": {
    "loan_amount": 50000000,
    "lender_name": "UniCredit",
    "decl_no_concordato": "DV_TRUE",
    "claim_amount": 30000000
  },
  "availability": {
    "document_processed": true,
    "has_text": true
  }
}
```

| Field | Tipe | Wajib | Keterangan |
|-------|------|-------|-----------|
| `query_id` | string | **Ya** | Identifier unik per request, dibuat oleh caller |
| `sector` | string | **Ya** | Nama sector: `"banking"`, `"finance"`, `"chatbot"` -- harus cocok dengan `KL_DOMAIN` |
| `observed` | object | Direkomendasikan | Merged field values dari semua Parser runs. Makin banyak field relevan, makin akurat scoring |
| `availability` | object | Tidak | Epistemic flags dari Parser SDK. Diterima HPVD tapi tidak dipakai -- diteruskan ke PMR dan Knowledge Builder di layer berikutnya |

> **Catatan `availability`:** HPVD adalah knowledge retrieval engine -- tugasnya hanya retrieve Policy/Product/RuleMapping yang relevan berdasarkan `observed`. Evaluasi `availability` adalah tanggung jawab PMR dan Knowledge Builder.

### 5.3 Contoh dengan `banking_parser_sdk`

```python
from banking_parser_sdk import run_parser, build_hpvd_query
import httpx

# Jalankan parser per document type
results = [
    run_parser("LENDER", {"lender_name": "UniCredit", "lender_code": "12345"}),
    run_parser("LOAN_INFORMATION", {"loan_amount": 50000000, "loan_contract_date": "2024-01-15"}),
    run_parser("LEGAL_DECLARATIONS", {"decl_no_concordato": "DV_TRUE"}),
]

# Build HPVD query dari merged results
payload = build_hpvd_query(results, sector="banking", query_id="REQ-001")

# Kirim ke HPVD
response = httpx.post("http://127.0.0.1:8000/query", json=payload)
result = response.json()
```

### 5.4 Contoh PowerShell

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/query `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "query_id": "REQ-001",
    "sector": "banking",
    "observed": {
      "loan_amount": 50000000,
      "lender_name": "UniCredit",
      "decl_no_concordato": "DV_TRUE"
    },
    "availability": {
      "document_processed": true
    }
  }' `
  | ConvertTo-Json -Depth 10
```

### 5.5 Response -- J14 (RetrievalRaw)

```json
{
  "schema_id": "manithy.hpvd_retrieval_raw.v1",
  "query_id": "REQ-001",
  "domain": "knowledge",
  "candidates": [
    {
      "candidate_id": "rule_mapping:MAP-BANKING-V3-RULES",
      "score": 1.0,
      "knowledge_type": "rule_mapping",
      "sector": "banking",
      "data": { ... },
      "provenance": {"source": "unknown"},
      "source_domain": "knowledge"
    },
    {
      "candidate_id": "policy:POL-BANKING-V1-COVERAGE",
      "score": 1.1,
      "knowledge_type": "policy",
      "sector": "banking",
      "data": { ... },
      "provenance": {},
      "source_domain": "knowledge"
    }
  ],
  "diagnostics": {
    "sector": "banking",
    "objects_considered": 3,
    "objects_returned": 2,
    "rule_mapping_forced": true
  }
}
```

> `rule_mapping` **selalu** disertakan dalam candidates, tanpa memandang scoring -- ini adalah mandatory retrieval per spec HPVD.

### 5.6 Response -- J16 (Family Assignment)

```json
{
  "schema_id": "manithy.analog_family_assignment.v1",
  "query_id": "REQ-001",
  "families": [
    {
      "family_id": "knowledge_policy",
      "members": [ ... ],
      "coherence": {"mean_confidence": 1.0, "dispersion": 0.0, "size": 1}
    },
    {
      "family_id": "knowledge_rule_mapping",
      "members": [ ... ],
      "coherence": {"mean_confidence": 1.0, "dispersion": 0.0, "size": 1}
    }
  ],
  "total_families": 2,
  "total_members": 2,
  "metadata": {"domain": "knowledge"}
}
```

---

## 6. Upload Knowledge Objects ke KL

Untuk menambah atau update data knowledge, gunakan script `scripts/seed_hpvd_knowledge.py`. **Setelah upload, server harus di-restart** agar corpus ter-reload.

### 6.1 Format Dokumen yang Didukung

Setiap file JSON harus punya **salah satu** key berikut di level root:

| Key | object_type | Kapan dipakai |
|-----|-------------|--------------|
| `policy_id` | `policy` | Aturan eligibility dan compliance |
| `product_id` | `product` | Konfigurasi produk (limit, tenor, rate) |
| `mapping_id` | `rule_mapping` | Gate + rules evaluasi (V3) |
| `doc_type` | `document_schema` | Inventori field yang dikenal sistem |

Dokumen dengan struktur lain (tidak punya salah satu key di atas) akan di-skip dengan WARNING.

### 6.2 Upload via Script

```powershell
# Dry run dulu
python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge --dry-run

# Upload beneran
python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge

# Upload file tertentu
python scripts/seed_hpvd_knowledge.py --files data/my_policy.json data/my_rules.json

# Dengan API key eksplisit
python scripts/seed_hpvd_knowledge.py --dir data/hpvd_knowledge --api-key kl_xxx
```

Satu file boleh berisi satu object atau array beberapa objects:

```json
[
  { "policy_id": "POL-001", "name": "Policy A", "eligibility_rules": {} },
  { "product_id": "PROD-001", "name": "Product B", "loan_constraints": {} }
]
```

---

## 7. Common Errors & Solusi

### E1 -- `corpus_size: 0` saat startup

**Gejala:** `/health` mengembalikan `corpus_size: 0`. Log menunjukkan semua dokumen di-skip.

**Penyebab & Solusi:**

| Penyebab | Indikator di log | Solusi |
|----------|-----------------|--------|
| `KL_API_KEY` tidak diset | `KL_API_KEY is not set` | Tambahkan ke `.env` |
| KL tidak bisa dijangkau | `KL /documents request failed` | Cek koneksi internet, cek status KL di Railway |
| Semua dokumen body kosong | `raw_text is not valid JSON ... char 0` | Dokumen di KL diupload tanpa `raw_text` -- re-upload menggunakan script seed |
| `object_type` tidak bisa di-infer | `Cannot infer object_type ... keys: [...]` | Dokumen tidak punya key `policy_id`/`product_id`/`mapping_id`/`doc_type` -- fix struktur JSON lalu re-upload |

---

### E2 -- `503 Service Unavailable` saat `POST /query`

**Gejala:**

```json
{"detail": "Knowledge corpus is empty — Knowledge Layer was unreachable at startup."}
```

**Penyebab:** Server startup sukses tapi corpus kosong (lihat E1).

**Solusi:** Atasi E1 terlebih dahulu, kemudian restart server.

---

### E3 -- `400 Bad Request`

**Gejala:**

```json
{"detail": "field required"}
```

**Penyebab:** Request body tidak menyertakan `query_id` atau `sector`.

**Solusi:** Pastikan kedua field tersebut ada di body:

```json
{
  "query_id": "REQ-001",
  "sector": "banking",
  "observed": {}
}
```

---

### E4 -- Browser loading tidak selesai (hang)

**Gejala:** Buka `http://localhost:8000/health` di browser Windows -- tidak pernah selesai.

**Penyebab:** Windows meresol `localhost` ke IPv6 (`::1`) tapi server hanya listen di IPv4.

**Solusi:** Gunakan IP eksplisit:

```
http://127.0.0.1:8000/health
```

Atau jalankan server dengan bind ke `127.0.0.1`:

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8000 --reload
```

---

### E5 -- Port 8000 sudah dipakai

**Gejala:**

```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```

**Solusi:** Ganti port:

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8001 --reload
```

Atau cari dan kill proses yang memakai port 8000:

```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

---

### E6 -- `ModuleNotFoundError: No module named 'fastapi'`

**Penyebab:** Dependency API belum terinstall.

**Solusi:**

```powershell
pip install -e ".[api]"
# atau manual:
pip install fastapi uvicorn httpx
```

---

### E7 -- Corpus ter-load tapi query tidak return kandidat

**Gejala:** `/health` menunjukkan `corpus_size > 0`, tapi `POST /query` mengembalikan `candidates: []`.

**Penyebab paling umum:** `sector` di request tidak cocok dengan `KL_DOMAIN` yang di-load.

**Cek:** Nilai `sector` di request harus sama persis dengan `KL_DOMAIN` di `.env` (case-sensitive).

```json
// .env: KL_DOMAIN=banking
{ "sector": "banking" }   // benar
{ "sector": "Banking" }   // salah -- case berbeda
{ "sector": "" }          // salah -- kosong, tidak ada filter sector
```

---

### E8 -- Swagger UI tidak bisa diakses

**Gejala:** `http://127.0.0.1:8000/docs` tidak muncul.

**Penyebab:** Server tidak berjalan, atau port berbeda.

**Cek:** Pastikan terminal menampilkan `Application startup complete.` dan tidak ada error. Gunakan port yang sama dengan yang dijalankan.

---

## Referensi

| Dokumen | Isi |
|---------|-----|
| [HPVD_CORE.md](HPVD_CORE.md) | Arsitektur internal, data model, retrieval pipeline |
| [MANITHY_INTEGRATION.md](MANITHY_INTEGRATION.md) | Posisi HPVD dalam pipeline Manithy v1, J-files reference |
| [CHANGELOG.md](CHANGELOG.md) | History versi dan capabilities |
| `src/hpvd/api.py` | Source code FastAPI app |
| `src/hpvd/kl_loader.py` | Source code KL corpus loader |
| `scripts/seed_hpvd_knowledge.py` | Script upload knowledge objects ke KL |
