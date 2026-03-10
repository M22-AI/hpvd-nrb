"""
Knowledge Layer Client
=======================

HTTP client for the Knowledge Layer API.
Supports document and event operations needed by HPVD.

Base URL default: https://knowledge-layer-production.up.railway.app
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx


# ---------------------------------------------------------------------------
# Response models (read-only dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class DocumentRead:
    """Parsed response from KL ``/documents`` endpoints."""
    id: str
    tenant_id: str
    title: str
    document_type: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentRead":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            title=data["title"],
            document_type=data.get("document_type"),
            created_by=data.get("created_by"),
            created_at=data.get("created_at"),
        )


@dataclass
class DocumentVersionRead:
    """Parsed response from KL ``/documents/{id}/versions`` endpoints."""
    id: str
    document_id: str
    version_number: int
    file_path: str
    file_size: Optional[int] = None
    checksum_sha256: Optional[str] = None
    uploaded_by: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentVersionRead":
        return cls(
            id=data["id"],
            document_id=data["document_id"],
            version_number=data["version_number"],
            file_path=data["file_path"],
            file_size=data.get("file_size"),
            checksum_sha256=data.get("checksum_sha256"),
            uploaded_by=data.get("uploaded_by"),
            created_at=data.get("created_at"),
        )


@dataclass
class EventRead:
    """Parsed response from KL ``/events`` endpoints."""
    id: str
    tenant_id: str
    event_kind: str
    payload: Dict[str, Any] = field(default_factory=dict)
    commit_id: Optional[str] = None
    previous_hash: Optional[str] = None
    event_hash: str = ""
    created_by: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventRead":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            event_kind=data["event_kind"],
            payload=data.get("payload", {}),
            commit_id=data.get("commit_id"),
            previous_hash=data.get("previous_hash"),
            event_hash=data.get("event_hash", ""),
            created_by=data.get("created_by"),
            created_at=data.get("created_at"),
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class KLClient:
    """
    Synchronous HTTP client for the Knowledge Layer API.

    Usage::

        client = KLClient()
        docs = client.list_documents("BANKING_CORE")
        doc = client.create_document("BANKING_CORE", "Loan Contract #123", "CONTRACT")
        version = client.upload_version(doc.id, pdf_bytes, uploaded_by="seed_script")
    """

    DEFAULT_BASE_URL = "https://knowledge-layer-production.up.railway.app"

    def __init__(self, base_url: Optional[str] = None, timeout: float = 30.0):
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=timeout)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Check if KL API is reachable (``GET /``)."""
        resp = self._client.get("/")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def create_document(
        self,
        tenant_id: str,
        title: str,
        document_type: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> DocumentRead:
        """Create a new document (``POST /documents``)."""
        payload: Dict[str, Any] = {"tenant_id": tenant_id, "title": title}
        if document_type is not None:
            payload["document_type"] = document_type
        if created_by is not None:
            payload["created_by"] = created_by

        resp = self._client.post("/documents", json=payload)
        resp.raise_for_status()
        return DocumentRead.from_dict(resp.json())

    def list_documents(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentRead]:
        """List documents for a tenant (``GET /documents``)."""
        resp = self._client.get(
            "/documents",
            params={"tenant_id": tenant_id, "limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return [DocumentRead.from_dict(d) for d in resp.json()]

    def get_document(self, document_id: str) -> DocumentRead:
        """Get a single document (``GET /documents/{document_id}``)."""
        resp = self._client.get(f"/documents/{document_id}")
        resp.raise_for_status()
        return DocumentRead.from_dict(resp.json())

    def upload_version(
        self,
        document_id: str,
        file_content: bytes,
        filename: str = "file.pdf",
        uploaded_by: Optional[str] = None,
    ) -> DocumentVersionRead:
        """Upload a new document version (``POST /documents/{id}/versions``)."""
        params: Dict[str, str] = {}
        if uploaded_by is not None:
            params["uploaded_by"] = uploaded_by

        files = {"file": (filename, file_content, "application/octet-stream")}
        resp = self._client.post(
            f"/documents/{document_id}/versions",
            files=files,
            params=params,
        )
        resp.raise_for_status()
        return DocumentVersionRead.from_dict(resp.json())

    def list_versions(self, document_id: str) -> List[DocumentVersionRead]:
        """List all versions of a document (``GET /documents/{id}/versions``)."""
        resp = self._client.get(f"/documents/{document_id}/versions")
        resp.raise_for_status()
        return [DocumentVersionRead.from_dict(v) for v in resp.json()]

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def create_event(
        self,
        tenant_id: str,
        event_kind: str,
        payload: Dict[str, Any],
        commit_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> EventRead:
        """Create a new event (``POST /events``)."""
        body: Dict[str, Any] = {
            "tenant_id": tenant_id,
            "event_kind": event_kind,
            "payload": payload,
        }
        if commit_id is not None:
            body["commit_id"] = commit_id
        if created_by is not None:
            body["created_by"] = created_by

        resp = self._client.post("/events", json=body)
        resp.raise_for_status()
        return EventRead.from_dict(resp.json())

    def list_events(
        self,
        tenant_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EventRead]:
        """List events for a tenant (``GET /events``)."""
        resp = self._client.get(
            "/events",
            params={"tenant_id": tenant_id, "limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return [EventRead.from_dict(e) for e in resp.json()]

    def verify_chain(self) -> Dict[str, Any]:
        """Verify event chain integrity (``GET /events/chain/verify``)."""
        resp = self._client.get("/events/chain/verify")
        resp.raise_for_status()
        return resp.json()
