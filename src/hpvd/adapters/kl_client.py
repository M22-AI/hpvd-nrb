"""
Knowledge Layer Client
=======================

HTTP client for the Knowledge Layer API.
Supports document, chunk, snapshot, and event operations needed by HPVD.

Base URL default: https://knowledge-layer-production.up.railway.app

Authentication:
    - Tenant operations: ``X-API-Key`` header (kl_...)
    - Admin operations: ``X-Admin-Key`` header (kla_...)
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import date, datetime

import httpx


# ---------------------------------------------------------------------------
# Response models (read-only dataclasses)
# ---------------------------------------------------------------------------

@dataclass
class DocumentMetadata:
    """Structured metadata for KL documents (G3 resolved)."""
    domain: Optional[str] = None
    action_class: Optional[str] = None
    phase_label: Optional[str] = None
    tags: Optional[List[str]] = None
    event_date: Optional[str] = None  # ISO date string

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DocumentMetadata":
        if not data:
            return cls()
        return cls(
            domain=data.get("domain"),
            action_class=data.get("action_class"),
            phase_label=data.get("phase_label"),
            tags=data.get("tags"),
            event_date=data.get("event_date"),
        )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {}
        if self.domain is not None:
            d["domain"] = self.domain
        if self.action_class is not None:
            d["action_class"] = self.action_class
        if self.phase_label is not None:
            d["phase_label"] = self.phase_label
        if self.tags is not None:
            d["tags"] = self.tags
        if self.event_date is not None:
            d["event_date"] = self.event_date
        return d


@dataclass
class DocumentRead:
    """Parsed response from KL ``/documents`` endpoints."""
    id: str
    tenant_id: str
    title: str
    document_type: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentRead":
        metadata_raw = data.get("metadata")
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            title=data["title"],
            document_type=data.get("document_type"),
            metadata=DocumentMetadata.from_dict(metadata_raw) if metadata_raw else None,
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
    raw_text: Optional[str] = None
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
            raw_text=data.get("raw_text"),
            uploaded_by=data.get("uploaded_by"),
            created_at=data.get("created_at"),
        )


@dataclass
class ChunkRead:
    """Parsed response from KL chunk endpoints (G2 resolved)."""
    id: str
    document_id: str
    version_number: int
    chunk_id: str
    sequence: int
    content: str
    checksum_sha256: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkRead":
        return cls(
            id=data["id"],
            document_id=data["document_id"],
            version_number=data["version_number"],
            chunk_id=data["chunk_id"],
            sequence=data["sequence"],
            content=data["content"],
            checksum_sha256=data["checksum_sha256"],
            metadata=data.get("metadata"),
            created_at=data.get("created_at"),
        )


@dataclass
class SnapshotItemRead:
    """A single document+version within a snapshot (G1 resolved)."""
    document_id: str
    version_number: int
    checksum_sha256: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnapshotItemRead":
        return cls(
            document_id=data["document_id"],
            version_number=data["version_number"],
            checksum_sha256=data["checksum_sha256"],
        )


@dataclass
class SnapshotRead:
    """Parsed response from KL ``/snapshots`` endpoints (G1+G4 resolved)."""
    id: str
    tenant_id: str
    snapshot_id: str
    description: Optional[str] = None
    ontology_version: str = ""
    calibration_model_version: str = ""
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    items: List[SnapshotItemRead] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SnapshotRead":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            snapshot_id=data["snapshot_id"],
            description=data.get("description"),
            ontology_version=data.get("ontology_version", ""),
            calibration_model_version=data.get("calibration_model_version", ""),
            created_by=data.get("created_by"),
            created_at=data.get("created_at"),
            items=[SnapshotItemRead.from_dict(i) for i in data.get("items", [])],
        )


@dataclass
class DocumentCandidateRead:
    """Lightweight document result from ``/documents/search/candidates`` (G6)."""
    document_id: str
    version_number: int
    checksum_sha256: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None
    snapshot_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentCandidateRead":
        metadata_raw = data.get("metadata")
        return cls(
            document_id=data["document_id"],
            version_number=data["version_number"],
            checksum_sha256=data.get("checksum_sha256"),
            metadata=DocumentMetadata.from_dict(metadata_raw) if metadata_raw else None,
            snapshot_id=data.get("snapshot_id"),
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


@dataclass
class TenantRead:
    """Parsed response from ``/tenants`` endpoints."""
    id: str
    name: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantRead":
        return cls(
            id=data["id"],
            name=data.get("name"),
            created_at=data.get("created_at"),
        )


@dataclass
class ApiKeyCreated:
    """Returned once at creation — includes the raw key."""
    id: str
    tenant_id: str
    name: str
    key_prefix: str
    is_active: bool
    raw_key: str
    expires_at: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApiKeyCreated":
        return cls(
            id=data["id"],
            tenant_id=data["tenant_id"],
            name=data["name"],
            key_prefix=data["key_prefix"],
            is_active=data["is_active"],
            raw_key=data["raw_key"],
            expires_at=data.get("expires_at"),
            created_at=data.get("created_at"),
        )


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class KLClient:
    """
    Synchronous HTTP client for the Knowledge Layer API.

    Usage::

        client = KLClient(api_key="kl_abc123")
        docs = client.list_documents(limit=50)
        snapshot = client.get_snapshot("PINSET_2026W10")
        chunks = client.list_chunks(doc.id, version_number=1)
    """

    DEFAULT_BASE_URL = "https://knowledge-layer-production.up.railway.app"

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        admin_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self._base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        headers: Dict[str, str] = {}
        if api_key:
            headers["X-API-Key"] = api_key
        if admin_key:
            headers["X-Admin-Key"] = admin_key
        self._client = httpx.Client(
            base_url=self._base_url,
            timeout=timeout,
            headers=headers,
        )

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
    # Tenants & API Keys (admin)
    # ------------------------------------------------------------------

    def create_tenant(
        self,
        name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> TenantRead:
        """Create a new tenant (``POST /tenants``). Requires admin key."""
        body: Dict[str, Any] = {}
        if tenant_id:
            body["id"] = tenant_id
        if name:
            body["name"] = name
        resp = self._client.post("/tenants", json=body)
        resp.raise_for_status()
        return TenantRead.from_dict(resp.json())

    def list_tenants(self) -> List[TenantRead]:
        """List all tenants (``GET /tenants``). Requires admin key."""
        resp = self._client.get("/tenants")
        resp.raise_for_status()
        return [TenantRead.from_dict(t) for t in resp.json()]

    def create_api_key(
        self,
        tenant_id: str,
        name: str,
        expires_at: Optional[str] = None,
    ) -> ApiKeyCreated:
        """Create an API key for a tenant (``POST /tenants/{id}/api-keys``). Requires admin key."""
        body: Dict[str, Any] = {"name": name}
        if expires_at:
            body["expires_at"] = expires_at
        resp = self._client.post(f"/tenants/{tenant_id}/api-keys", json=body)
        resp.raise_for_status()
        return ApiKeyCreated.from_dict(resp.json())

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def create_document(
        self,
        title: str,
        document_type: Optional[str] = None,
        metadata: Optional[DocumentMetadata] = None,
        created_by: Optional[str] = None,
    ) -> DocumentRead:
        """Create a new document (``POST /documents``)."""
        payload: Dict[str, Any] = {"title": title}
        if document_type is not None:
            payload["document_type"] = document_type
        if metadata is not None:
            payload["metadata"] = metadata.to_dict()
        if created_by is not None:
            payload["created_by"] = created_by

        resp = self._client.post("/documents", json=payload)
        resp.raise_for_status()
        return DocumentRead.from_dict(resp.json())

    def list_documents(
        self,
        document_type: Optional[str] = None,
        domain: Optional[str] = None,
        action_class: Optional[str] = None,
        phase_label: Optional[str] = None,
        tag: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentRead]:
        """List documents with optional filters (``GET /documents``)."""
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if document_type:
            params["document_type"] = document_type
        if domain:
            params["domain"] = domain
        if action_class:
            params["action_class"] = action_class
        if phase_label:
            params["phase_label"] = phase_label
        if tag:
            params["tag"] = tag
        if from_date:
            params["from_date"] = from_date
        if to_date:
            params["to_date"] = to_date

        resp = self._client.get("/documents", params=params)
        resp.raise_for_status()
        return [DocumentRead.from_dict(d) for d in resp.json()]

    def get_document(self, document_id: str) -> DocumentRead:
        """Get a single document (``GET /documents/{document_id}``)."""
        resp = self._client.get(f"/documents/{document_id}")
        resp.raise_for_status()
        return DocumentRead.from_dict(resp.json())

    def search_documents(
        self,
        document_type: Optional[str] = None,
        domain: Optional[str] = None,
        action_class: Optional[str] = None,
        phase_label: Optional[str] = None,
        tag: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        preset: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentRead]:
        """Search documents (``POST /documents/search``)."""
        body: Dict[str, Any] = {"limit": limit, "offset": offset}
        if document_type:
            body["document_type"] = document_type
        if domain:
            body["domain"] = domain
        if action_class:
            body["action_class"] = action_class
        if phase_label:
            body["phase_label"] = phase_label
        if tag:
            body["tag"] = tag
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        if from_date or to_date or preset:
            body["temporal_scope"] = {}
            if from_date:
                body["temporal_scope"]["from_date"] = from_date
            if to_date:
                body["temporal_scope"]["to_date"] = to_date
            if preset:
                body["temporal_scope"]["preset"] = preset

        resp = self._client.post("/documents/search", json=body)
        resp.raise_for_status()
        return [DocumentRead.from_dict(d) for d in resp.json()]

    def search_candidates(
        self,
        document_type: Optional[str] = None,
        domain: Optional[str] = None,
        action_class: Optional[str] = None,
        phase_label: Optional[str] = None,
        tag: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        preset: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[DocumentCandidateRead]:
        """Search document candidates (``POST /documents/search/candidates``)."""
        body: Dict[str, Any] = {"limit": limit, "offset": offset}
        if document_type:
            body["document_type"] = document_type
        if domain:
            body["domain"] = domain
        if action_class:
            body["action_class"] = action_class
        if phase_label:
            body["phase_label"] = phase_label
        if tag:
            body["tag"] = tag
        if snapshot_id:
            body["snapshot_id"] = snapshot_id
        if from_date or to_date or preset:
            body["temporal_scope"] = {}
            if from_date:
                body["temporal_scope"]["from_date"] = from_date
            if to_date:
                body["temporal_scope"]["to_date"] = to_date
            if preset:
                body["temporal_scope"]["preset"] = preset

        resp = self._client.post("/documents/search/candidates", json=body)
        resp.raise_for_status()
        return [DocumentCandidateRead.from_dict(d) for d in resp.json()]

    # ------------------------------------------------------------------
    # Document Versions
    # ------------------------------------------------------------------

    def upload_version(
        self,
        document_id: str,
        file_content: bytes,
        filename: str = "file.pdf",
        raw_text: Optional[str] = None,
        uploaded_by: Optional[str] = None,
    ) -> DocumentVersionRead:
        """Upload a new document version (``POST /documents/{id}/versions``)."""
        params: Dict[str, str] = {}
        if uploaded_by is not None:
            params["uploaded_by"] = uploaded_by

        files: Dict[str, Any] = {
            "file": (filename, file_content, "application/octet-stream"),
        }
        data: Dict[str, str] = {}
        if raw_text is not None:
            data["raw_text"] = raw_text

        resp = self._client.post(
            f"/documents/{document_id}/versions",
            files=files,
            data=data if data else None,
            params=params,
        )
        resp.raise_for_status()
        return DocumentVersionRead.from_dict(resp.json())

    def list_versions(self, document_id: str) -> List[DocumentVersionRead]:
        """List all versions of a document (``GET /documents/{id}/versions``)."""
        resp = self._client.get(f"/documents/{document_id}/versions")
        resp.raise_for_status()
        return [DocumentVersionRead.from_dict(v) for v in resp.json()]

    def download_content(
        self,
        document_id: str,
        version_number: int,
    ) -> bytes:
        """Download file content of a document version (``GET .../content``). G5 resolved."""
        resp = self._client.get(
            f"/documents/{document_id}/versions/{version_number}/content"
        )
        resp.raise_for_status()
        return resp.content

    # ------------------------------------------------------------------
    # Chunks (G2 resolved)
    # ------------------------------------------------------------------

    def create_chunks(
        self,
        document_id: str,
        version_number: int,
        chunks: List[Dict[str, Any]],
    ) -> List[ChunkRead]:
        """
        Create chunks for a document version (``POST .../chunks``).

        Each chunk dict should have: chunk_id, content, sequence, metadata (optional).
        """
        resp = self._client.post(
            f"/documents/{document_id}/versions/{version_number}/chunks",
            json=chunks,
        )
        resp.raise_for_status()
        return [ChunkRead.from_dict(c) for c in resp.json()]

    def list_chunks(
        self,
        document_id: str,
        version_number: int,
    ) -> List[ChunkRead]:
        """List all chunks of a document version (``GET .../chunks``)."""
        resp = self._client.get(
            f"/documents/{document_id}/versions/{version_number}/chunks"
        )
        resp.raise_for_status()
        return [ChunkRead.from_dict(c) for c in resp.json()]

    def get_chunk(
        self,
        document_id: str,
        version_number: int,
        chunk_id: str,
    ) -> ChunkRead:
        """Get a single chunk (``GET .../chunks/{chunk_id}``)."""
        resp = self._client.get(
            f"/documents/{document_id}/versions/{version_number}/chunks/{chunk_id}"
        )
        resp.raise_for_status()
        return ChunkRead.from_dict(resp.json())

    # ------------------------------------------------------------------
    # Snapshots (G1 + G4 resolved)
    # ------------------------------------------------------------------

    def create_snapshot(
        self,
        snapshot_id: str,
        ontology_version: str,
        calibration_model_version: str,
        items: List[Dict[str, Any]],
        description: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> SnapshotRead:
        """
        Create an immutable snapshot (``POST /snapshots``).

        Each item dict should have: document_id, version_number.
        """
        body: Dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "ontology_version": ontology_version,
            "calibration_model_version": calibration_model_version,
            "items": items,
        }
        if description:
            body["description"] = description
        if created_by:
            body["created_by"] = created_by

        resp = self._client.post("/snapshots", json=body)
        resp.raise_for_status()
        return SnapshotRead.from_dict(resp.json())

    def list_snapshots(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """List snapshots (``GET /snapshots``). Returns summary items without full item lists."""
        resp = self._client.get(
            "/snapshots", params={"limit": limit, "offset": offset}
        )
        resp.raise_for_status()
        return resp.json()

    def get_snapshot(self, snapshot_id: str) -> SnapshotRead:
        """Get a snapshot with all items (``GET /snapshots/{snapshot_id}``)."""
        resp = self._client.get(f"/snapshots/{snapshot_id}")
        resp.raise_for_status()
        return SnapshotRead.from_dict(resp.json())

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def create_event(
        self,
        event_kind: str,
        payload: Dict[str, Any],
        commit_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> EventRead:
        """Create a new event (``POST /events``)."""
        body: Dict[str, Any] = {
            "event_kind": event_kind,
            "commit_id": commit_id or "",
            "payload": payload,
        }
        if created_by is not None:
            body["created_by"] = created_by

        resp = self._client.post("/events", json=body)
        resp.raise_for_status()
        return EventRead.from_dict(resp.json())

    def list_events(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> List[EventRead]:
        """List events (``GET /events``)."""
        resp = self._client.get(
            "/events",
            params={"limit": limit, "offset": offset},
        )
        resp.raise_for_status()
        return [EventRead.from_dict(e) for e in resp.json()]

    def verify_chain(self) -> Dict[str, Any]:
        """Verify event chain integrity (``GET /events/chain/verify``)."""
        resp = self._client.get("/events/chain/verify")
        resp.raise_for_status()
        return resp.json()
