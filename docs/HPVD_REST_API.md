# HPVD REST API ù Deployment & Integration Guide

> This document is intended for **external teams** (Parser, NRB, PMR) that will call HPVD as a REST service in the Manithy v1 pipeline. For HPVD internal architecture, see [HPVD_CORE.md](HPVD_CORE.md). For HPVD's position in the Manithy pipeline, see [MANITHY_INTEGRATION.md](MANITHY_INTEGRATION.md).

**Version:** 1.0.0-alpha3 | **Framework:** FastAPI + Uvicorn | **Python:** 3.10+

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Setup & Configuration](#2-setup--configuration)
3. [Running the Server](#3-running-the-server)
4. [Endpoints](#4-endpoints)
5. [Request & Response Format (Parser SDK Output)](#5-request--response-format-parser-sdk-output)
6. [Upload Knowledge Objects to KL](#6-upload-knowledge-objects-to-kl)
7. [Common Errors & Solutions](#7-common-errors--solutions)

---

## 1. Prerequisites

| Requirement | Minimum version | Notes |
|-----------|--------------|---------|
| Python | 3.10 | `venv` included |
| pip | latest | `pip install --upgrade pip` |
| Internet access | -- | Required to fetch corpus from KL at startup |
| KL API Key | -- | `kl_...` format, request from the KL team |

---

## 2. Setup & Configuration

### 2.1 Clone & Install

```powershell
git clone <repo-url>
cd hpvd-nrb

python -m venv venv
venv\Scripts\Activate.ps1

pip install -e ".[api]"
```

> If `pip install -e ".[api]"` fails, install manually:
> ```powershell
> pip install fastapi>=0.110.0 uvicorn>=0.29.0 httpx>=0.27.0 python-dotenv
> pip install -e .
> ```

### 2.2 Environment Configuration

Create a `.env` file in the project root (or copy from `.env.example`):

```env
KL_API_KEY=kl_your_key_here
KL_BASE_URL=https://knowledge-layer-production.up.railway.app
KL_DOMAIN=banking
```

| Variable | Required | Description |
|----------|-------|-----------|
| `KL_API_KEY` | Yes | KL tenant API key (`kl_...` format) |
| `KL_BASE_URL` | No | Default: `https://knowledge-layer-production.up.railway.app` |
| `KL_DOMAIN` | No | Domain/sector to load. Default: `banking` |

> **Important:** The `.env` file is already in `.gitignore` -- do not commit this file.

---

## 3. Running the Server

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8000 --reload
```

> **Windows:** Always use `127.0.0.1`, not `0.0.0.0`, for local browser access.
> `0.0.0.0` is used when the server must be accessible from other machines on the network (for example Docker or VM).

At startup, HPVD will:
1. Load `.env`
2. Fetch all documents from KL (`GET /documents?domain=banking`)
3. Parse and infer `object_type` from each document content
4. Build in-memory index
5. Log the number of objects successfully loaded

Expected normal startup logs:

```
INFO:     Application startup complete.
INFO:hpvd.kl_loader:KLCorpusLoader: loaded 3 objects, skipped 1 (domain=banking)
INFO:src.hpvd.api:HPVD API ready -- 3 knowledge objects loaded (domain=banking)
```

### Verification

```powershell
# Open in browser
http://127.0.0.1:8000/health

# Or via PowerShell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

Expected response:

```json
{"status": "ok", "corpus_size": 3, "domain": "banking"}
```

> `corpus_size: 0` means no documents were successfully loaded from KL. See [Section 7](#7-common-errors--solutions).

---

## 4. Endpoints

### `GET /health`

Liveness check and corpus status.

**Response:**

```json
{
  "status": "ok",
  "corpus_size": 3,
  "domain": "banking"
}
```

| Field | Type | Description |
|-------|------|-----------|
| `status` | string | Always `"ok"` when the server is running |
| `corpus_size` | int | Number of loaded knowledge objects |
| `domain` | string | Active domain (from `KL_DOMAIN`) |

---

### `POST /query`

Accept Parser SDK output, run retrieval pipeline, return J14 + J15 + J16.

**Request:** `Content-Type: application/json`

Input is direct output from `banking_parser_sdk` -- see [Section 5](#5-request--response-format-parser-sdk-output) for full format.

**Response:**

```json
{
  "j14": { ... },
  "j15": { ... },
  "j16": { ... }
}
```

**HTTP Status Codes:**

| Code | Condition |
|------|---------|
| `200` | Success |
| `400` | Malformed request -- `query_id` or `sector` missing |
| `503` | Empty corpus -- KL unreachable at startup |
| `500` | Unexpected internal error |

---

## 5. Request & Response Format (Parser SDK Output)

### 5.1 Position in the Pipeline

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

HPVD accepts the Parser SDK format directly. Adaptation to internal pipeline format is handled inside HPVD -- the caller does not need internal implementation details.

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

| Field | Type | Required | Description |
|-------|------|-------|-----------|
| `query_id` | string | **Yes** | Unique identifier per request, created by caller |
| `sector` | string | **Yes** | Sector name: `"banking"`, `"finance"`, `"chatbot"` -- must match `KL_DOMAIN` |
| `observed` | object | Recommended | Merged field values from all Parser runs. More relevant fields generally improve scoring accuracy |
| `availability` | object | No | Epistemic flags from Parser SDK. Accepted by HPVD but unused -- forwarded to PMR and Knowledge Builder in the next layer |

> **Note on `availability`:** HPVD is a knowledge retrieval engine -- its job is only to retrieve relevant Policy/Product/RuleMapping based on `observed`. `availability` evaluation is the responsibility of PMR and Knowledge Builder.

### 5.3 Example with `banking_parser_sdk`

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

### 5.4 PowerShell Example

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

> `rule_mapping` is **always** included in candidates, regardless of scoring -- this is mandatory retrieval per HPVD spec.

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

## 6. Upload Knowledge Objects to KL

To add or update knowledge data, use the `scripts/seed_hpvd_knowledge.py` script. **After upload, the server must be restarted** so the corpus reloads.

### 6.1 Supported Document Format

Each JSON file must contain **one of** the following keys at root level:

| Key | object_type | When to use |
|-----|-------------|--------------|
| `policy_id` | `policy` | Eligibility and compliance rules |
| `product_id` | `product` | Product configuration (limit, tenor, rate) |
| `mapping_id` | `rule_mapping` | Evaluation gate + rules (V3) |
| `doc_type` | `document_schema` | Inventory of system-recognized fields |

Documents with other structures (without one of the keys above) will be skipped with a WARNING.

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

A file may contain one object or an array of multiple objects:

```json
[
  { "policy_id": "POL-001", "name": "Policy A", "eligibility_rules": {} },
  { "product_id": "PROD-001", "name": "Product B", "loan_constraints": {} }
]
```

---

## 7. Common Errors & Solutions

### E1 -- `corpus_size: 0` at startup

**Symptoms:** `/health` returns `corpus_size: 0`. Logs show all documents are skipped.

**Causes & Solutions:**

| Cause | Log indicator | Solution |
|----------|-----------------|--------|
| `KL_API_KEY` not set | `KL_API_KEY is not set` | Add it to `.env` |
| KL unreachable | `KL /documents request failed` | Check internet connectivity, check KL status on Railway |
| All document bodies are empty | `raw_text is not valid JSON ... char 0` | Documents in KL were uploaded without `raw_text` -- re-upload using the seed script |
| `object_type` cannot be inferred | `Cannot infer object_type ... keys: [...]` | Document does not have `policy_id`/`product_id`/`mapping_id`/`doc_type` key -- fix JSON structure then re-upload |

---

### E2 -- `503 Service Unavailable` on `POST /query`

**Symptoms:**

```json
{"detail": "Knowledge corpus is empty ù Knowledge Layer was unreachable at startup."}
```

**Cause:** Server startup succeeded but corpus is empty (see E1).

**Solution:** Resolve E1 first, then restart the server.

---

### E3 -- `400 Bad Request`

**Symptoms:**

```json
{"detail": "field required"}
```

**Cause:** Request body does not include `query_id` or `sector`.

**Solution:** Ensure both fields are present in the body:

```json
{
  "query_id": "REQ-001",
  "sector": "banking",
  "observed": {}
}
```

---

### E4 -- Browser loading never finishes (hang)

**Symptoms:** Open `http://localhost:8000/health` in Windows browser -- it never finishes.

**Cause:** Windows resolves `localhost` to IPv6 (`::1`) but the server listens only on IPv4.

**Solution:** Use explicit IP:

```
http://127.0.0.1:8000/health
```

Or run the server with bind to `127.0.0.1`:

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8000 --reload
```

---

### E5 -- Port 8000 already in use

**Symptoms:**

```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```

**Solution:** Change port:

```powershell
uvicorn src.hpvd.api:app --host 127.0.0.1 --port 8001 --reload
```

Or find and kill the process using port 8000:

```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

---

### E6 -- `ModuleNotFoundError: No module named 'fastapi'`

**Cause:** API dependencies are not installed.

**Solution:**

```powershell
pip install -e ".[api]"
# atau manual:
pip install fastapi uvicorn httpx
```

---

### E7 -- Corpus loaded but query returns no candidates

**Symptoms:** `/health` shows `corpus_size > 0`, but `POST /query` returns `candidates: []`.

**Most common cause:** `sector` in the request does not match loaded `KL_DOMAIN`.

**Check:** `sector` value in the request must exactly match `KL_DOMAIN` in `.env` (case-sensitive).

```json
// .env: KL_DOMAIN=banking
{ "sector": "banking" }   // benar
{ "sector": "Banking" }   // salah -- case berbeda
{ "sector": "" }          // salah -- kosong, tidak ada filter sector
```

---

### E8 -- Swagger UI is inaccessible

**Symptoms:** `http://127.0.0.1:8000/docs` does not appear.

**Cause:** Server is not running, or using a different port.

**Check:** Ensure terminal shows `Application startup complete.` and no errors. Use the same port as the running server.

---

## References

| Document | Content |
|---------|-----|
| [HPVD_CORE.md](HPVD_CORE.md) | Internal architecture, data model, retrieval pipeline |
| [MANITHY_INTEGRATION.md](MANITHY_INTEGRATION.md) | HPVD position in Manithy v1 pipeline, J-files reference |
| [CHANGELOG.md](CHANGELOG.md) | Version history and capabilities |
| `src/hpvd/api.py` | Source code FastAPI app |
| `src/hpvd/kl_loader.py` | Source code KL corpus loader |
| `scripts/seed_hpvd_knowledge.py` | Script to upload knowledge objects to KL |
