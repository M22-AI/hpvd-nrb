"""
Knowledge Layer Corpus Loader
==============================

Loads the full corpus from the Knowledge Layer REST API at startup.

Flow (6 steps):
    1. GET /documents?domain={domain}&limit=50  → list of documents
    2. GET /documents/{doc_id}/versions          → pick highest version_number
    3. GET /documents/{doc_id}/versions/{v}/content → raw_text (JSON string)
    4. Parse raw_text as JSON dict
    5. Infer object_type from dict keys
    6. Inject object_type + sector, append to corpus

Authentication: X-API-Key header on every request.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_INFER_MAP: list[tuple[str, str]] = [
    ("policy_id", "policy"),
    ("product_id", "product"),
    ("mapping_id", "rule_mapping"),
    ("doc_type", "document_schema"),
]


class KLCorpusLoader:
    """Load a knowledge corpus from the Knowledge Layer REST API.

    Parameters
    ----------
    base_url:
        Base URL of the KL API (no trailing slash).
    api_key:
        Value for the ``X-API-Key`` header.
    domain:
        KL domain to load (e.g. ``"banking"``).  Mapped to HPVD ``sector``.
    """

    def __init__(self, base_url: str, api_key: str, domain: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._domain = domain
        self._headers = {"X-API-Key": api_key}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def load_corpus(self) -> list[dict]:
        """Fetch and return all parseable knowledge objects for the domain.

        Each returned dict has:
            - All fields from the raw document JSON
            - ``"object_type"``: inferred from content keys
            - ``"sector"``: copied from KL ``domain``

        Documents whose content cannot be parsed or whose object_type
        cannot be inferred are skipped with a WARNING log.

        Returns
        -------
        list[dict]
            Ready for ``KnowledgeRetrievalStrategy.build_index()``.
        """
        documents = self._fetch_documents()
        corpus: list[dict] = []
        skipped = 0

        for doc in documents:
            doc_id = doc.get("document_id") or doc.get("id")
            if not doc_id:
                logger.warning("KL document entry missing document_id — skipping: %s", doc)
                skipped += 1
                continue

            version_number, raw_text = self._fetch_latest_version(doc_id)
            if version_number is None:
                logger.warning("No versions found for document_id=%s — skipping", doc_id)
                skipped += 1
                continue

            # raw_text may already be embedded in the version record (preferred path).
            # If not, fall back to the /content endpoint.
            if not raw_text:
                raw_text = self._fetch_content(doc_id, version_number)

            if not raw_text:
                logger.warning(
                    "No content for document_id=%s version=%s — skipping", doc_id, version_number
                )
                skipped += 1
                continue

            obj = self._parse_raw_text(doc_id, raw_text)
            if obj is None:
                skipped += 1
                continue

            object_type = self._infer_object_type(obj)
            if object_type is None:
                logger.warning(
                    "Cannot infer object_type for document_id=%s "
                    "(keys: %s) — skipping",
                    doc_id,
                    list(obj.keys()),
                )
                skipped += 1
                continue

            obj["object_type"] = object_type
            obj["sector"] = self._domain
            corpus.append(obj)

        logger.info(
            "KLCorpusLoader: loaded %d objects, skipped %d (domain=%s)",
            len(corpus),
            skipped,
            self._domain,
        )
        return corpus

    def _infer_object_type(self, obj: dict) -> Optional[str]:
        """Return the object_type inferred from *obj* keys, or ``None``.

        Inference priority: policy_id > product_id > mapping_id > doc_type.
        """
        for key, object_type in _INFER_MAP:
            if key in obj:
                return object_type
        return None

    # ------------------------------------------------------------------
    # Private — HTTP helpers
    # ------------------------------------------------------------------

    def _fetch_documents(self) -> list[dict]:
        """Step 1: GET /documents?domain={domain}&limit=50."""
        url = f"{self._base_url}/documents"
        params = {"domain": self._domain, "limit": 50}
        try:
            response = httpx.get(url, headers=self._headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            # KL may return a list directly or wrap it in {"documents": [...]}
            if isinstance(data, list):
                return data
            return data.get("documents") or data.get("data") or []
        except httpx.HTTPError as exc:
            logger.error("KL /documents request failed: %s", exc)
            return []

    def _fetch_latest_version(self, document_id: str) -> tuple[Optional[int], Optional[str]]:
        """Step 2: GET /documents/{id}/versions → (highest version_number, raw_text).

        ``raw_text`` is returned if the KL version record already embeds it
        (uploaded via ``raw_text`` form field).  Otherwise it is ``None`` and
        the caller must fall back to the ``/content`` endpoint.
        """
        url = f"{self._base_url}/documents/{document_id}/versions"
        try:
            response = httpx.get(url, headers=self._headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            versions: list[dict] = (
                data if isinstance(data, list) else data.get("versions") or data.get("data") or []
            )
            if not versions:
                return None, None
            latest = max(versions, key=lambda v: v.get("version_number", 0))
            return latest.get("version_number"), latest.get("raw_text")
        except httpx.HTTPError as exc:
            logger.error(
                "KL /documents/%s/versions request failed: %s", document_id, exc
            )
            return None, None

    def _fetch_content(self, document_id: str, version_number: int) -> Optional[str]:
        """Step 3: GET /documents/{id}/versions/{v}/content → raw_text string.

        The KL API may return the content as:
          (a) a JSON envelope  {"raw_text": "...", ...}
          (b) the raw document text directly as the response body (plain text / JSON string)

        Both cases are handled: try JSON-parse first; if that yields a dict with
        ``raw_text``/``content``, extract it.  Otherwise treat the body itself as
        the raw_text (covers both plain-text and direct JSON-string responses).
        """
        url = f"{self._base_url}/documents/{document_id}/versions/{version_number}/content"
        try:
            response = httpx.get(url, headers=self._headers, timeout=30)
            response.raise_for_status()

            body = response.text
            if not body or not body.strip():
                logger.warning(
                    "KL /documents/%s/versions/%s/content returned empty body",
                    document_id,
                    version_number,
                )
                return None

            # Try to parse as JSON envelope first
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    raw_text = data.get("raw_text") or data.get("content")
                    if raw_text is not None:
                        return str(raw_text)
                # JSON parsed but no expected key — fall through and use body as-is
            except json.JSONDecodeError:
                pass

            # Body is already the raw_text (plain text or a JSON string)
            return body

        except httpx.HTTPError as exc:
            logger.error(
                "KL /documents/%s/versions/%s/content request failed: %s",
                document_id,
                version_number,
                exc,
            )
            return None

    def _parse_raw_text(self, document_id: str, raw_text: str) -> Optional[dict]:
        """Step 4: Parse raw_text as a JSON dict."""
        try:
            obj = json.loads(raw_text)
            if not isinstance(obj, dict):
                logger.warning(
                    "document_id=%s raw_text parsed to %s (expected dict) — skipping",
                    document_id,
                    type(obj).__name__,
                )
                return None
            return obj
        except json.JSONDecodeError as exc:
            logger.warning(
                "document_id=%s raw_text is not valid JSON: %s — skipping",
                document_id,
                exc,
            )
            return None
