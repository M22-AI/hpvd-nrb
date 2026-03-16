"""
KL Document Loader
===================

Fetches documents and **chunks** from the Knowledge Layer API and converts
them into ``DocumentChunk`` objects consumable by ``DocumentRetrievalStrategy``.

Now uses KL-managed chunks (G2 resolved) — each document version can have
chunks stored in KL. The loader fetches these chunks directly, using their
actual content instead of the old title-as-content workaround.

Supports three loading modes:
1. ``load_as_chunks()`` — List documents → fetch chunks for each
2. ``load_from_snapshot()`` — Resolve snapshot → get pinned items → fetch chunks
3. ``load_with_search()`` — Search documents with filters → fetch chunks
"""

from typing import Any, Dict, List, Optional

from .kl_client import (
    KLClient,
    DocumentRead,
    DocumentMetadata,
    ChunkRead,
    SnapshotRead,
)
from .strategies.document_strategy import DocumentChunk


# ---------------------------------------------------------------------------
# Document type → topic mapping
# ---------------------------------------------------------------------------

DOC_TYPE_TO_TOPIC: Dict[str, str] = {
    "INTIMAZIONE": "legal_notice",
    "PEC_RECEIPT": "legal_notice",
    "CREDIT_SPECIFICATION": "credit_analysis",
    "IDENTITY_DOC": "identity",
    "DELIBERA": "bank_decision",
    "CONTRACT": "contract",
    "EROGAZIONE": "disbursement",
    "AMMORTAMENTO": "repayment_plan",
    "CREDIT_REPORT": "credit_analysis",
    "RISK_DECLARATION": "risk_assessment",
    "RATE_DECLARATION": "risk_assessment",
    "NO_DEFAULT": "compliance",
    "NO_PREJUDICE": "compliance",
    "ESITO_LETTER": "outcome",
    "ESCUSSIONE_CHECK": "credit_analysis",
    "INDUSTRIAL_PLAN": "financial_plan",
    "PROPERTY_SURVEY": "collateral",
    "FIDEJUSSIONE": "guarantee",
    "BALANCE_SHEET": "financial_plan",
    # Fallback
    "POLICY_TEXT": "policy",
    "FAQ": "faq",
    "GUIDE": "guide",
}


def _map_topic(
    document_type: Optional[str],
    metadata: Optional[DocumentMetadata] = None,
) -> str:
    """
    Map a KL document to a topic label for HPVD.

    Prefers ``metadata.domain`` if available, falls back to
    ``document_type`` mapping.
    """
    # Prefer metadata.domain if set
    if metadata and metadata.domain:
        return metadata.domain.lower()
    if not document_type:
        return "unknown"
    return DOC_TYPE_TO_TOPIC.get(document_type.upper(), document_type.lower())


class KLDocumentLoader:
    """
    Loads documents and chunks from KL, converting to ``DocumentChunk`` lists.

    Usage::

        client = KLClient(api_key="kl_abc123")
        loader = KLDocumentLoader(client)

        # Mode 1: Load all documents + their chunks
        chunks = loader.load_as_chunks()

        # Mode 2: Load from a pinned snapshot
        chunks = loader.load_from_snapshot("PINSET_2026W10")

        # Mode 3: Load with search filters
        chunks = loader.load_with_search(
            domain="finance",
            action_class="TRADE_EXECUTION",
        )
    """

    def __init__(self, client: KLClient):
        self._client = client

    # ------------------------------------------------------------------
    # Mode 1: Load all documents → fetch chunks
    # ------------------------------------------------------------------

    def load_as_chunks(
        self,
        limit: int = 200,
        document_type: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> List[DocumentChunk]:
        """
        Fetch documents and convert to chunks.

        If KL-managed chunks exist for a document version, uses those.
        Otherwise falls back to synthetic chunk from document title/metadata.
        """
        documents = self._client.list_documents(
            document_type=document_type,
            domain=domain,
            limit=limit,
        )
        return self._documents_to_chunks(documents)

    # ------------------------------------------------------------------
    # Mode 2: Load from snapshot (G1 resolved)
    # ------------------------------------------------------------------

    def load_from_snapshot(
        self,
        snapshot_id: str,
    ) -> List[DocumentChunk]:
        """
        Resolve a snapshot → get pinned document versions → fetch chunks.

        Returns ``DocumentChunk`` list with snapshot lineage in metadata.
        """
        snapshot = self._client.get_snapshot(snapshot_id)
        all_chunks: List[DocumentChunk] = []

        for item in snapshot.items:
            # Fetch document for metadata
            try:
                doc = self._client.get_document(item.document_id)
            except Exception:
                doc = None

            # Fetch KL-managed chunks for this pinned version
            try:
                kl_chunks = self._client.list_chunks(
                    item.document_id, item.version_number
                )
            except Exception:
                kl_chunks = []

            if kl_chunks:
                for kl_chunk in kl_chunks:
                    chunk = self._kl_chunk_to_document_chunk(
                        kl_chunk, doc, snapshot=snapshot
                    )
                    all_chunks.append(chunk)
            elif doc:
                # Fallback: synthetic chunk from doc title
                chunk = self._document_to_synthetic_chunk(
                    doc,
                    version_number=item.version_number,
                    checksum=item.checksum_sha256,
                    snapshot=snapshot,
                )
                all_chunks.append(chunk)

        return all_chunks

    # ------------------------------------------------------------------
    # Mode 3: Search-based loading (G6 resolved)
    # ------------------------------------------------------------------

    def load_with_search(
        self,
        domain: Optional[str] = None,
        action_class: Optional[str] = None,
        phase_label: Optional[str] = None,
        tag: Optional[str] = None,
        snapshot_id: Optional[str] = None,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        preset: Optional[str] = None,
        limit: int = 50,
    ) -> List[DocumentChunk]:
        """
        Search documents with metadata filters → fetch chunks.

        Uses ``POST /documents/search`` for filtered retrieval.
        """
        documents = self._client.search_documents(
            domain=domain,
            action_class=action_class,
            phase_label=phase_label,
            tag=tag,
            snapshot_id=snapshot_id,
            from_date=from_date,
            to_date=to_date,
            preset=preset,
            limit=limit,
        )
        return self._documents_to_chunks(documents)

    # ------------------------------------------------------------------
    # Internal: Convert documents to chunks
    # ------------------------------------------------------------------

    def _documents_to_chunks(
        self,
        documents: List[DocumentRead],
    ) -> List[DocumentChunk]:
        """Convert a list of KL documents to DocumentChunks, fetching KL chunks."""
        all_chunks: List[DocumentChunk] = []

        for doc in documents:
            # Try to fetch KL-managed chunks from latest version
            kl_chunks = self._fetch_latest_chunks(doc.id)

            if kl_chunks:
                for kl_chunk in kl_chunks:
                    chunk = self._kl_chunk_to_document_chunk(kl_chunk, doc)
                    all_chunks.append(chunk)
            else:
                # Fallback: synthetic chunk from title + metadata
                chunk = self._document_to_synthetic_chunk(doc)
                all_chunks.append(chunk)

        return all_chunks

    def _fetch_latest_chunks(self, document_id: str) -> List[ChunkRead]:
        """Fetch chunks from the latest version of a document."""
        try:
            versions = self._client.list_versions(document_id)
            if not versions:
                return []
            latest = max(versions, key=lambda v: v.version_number)
            return self._client.list_chunks(document_id, latest.version_number)
        except Exception:
            return []

    def _kl_chunk_to_document_chunk(
        self,
        kl_chunk: ChunkRead,
        doc: Optional[DocumentRead] = None,
        snapshot: Optional[SnapshotRead] = None,
    ) -> DocumentChunk:
        """Convert a KL ChunkRead to a HPVD DocumentChunk."""
        # Determine topic from document metadata or chunk metadata
        doc_type = doc.document_type if doc else None
        doc_meta = doc.metadata if doc else None
        topic = _map_topic(doc_type, doc_meta)

        # Build metadata
        metadata: Dict[str, Any] = {
            "kl_document_id": kl_chunk.document_id,
            "kl_chunk_id": kl_chunk.chunk_id,
            "version_number": kl_chunk.version_number,
            "sequence": kl_chunk.sequence,
            "checksum_sha256": kl_chunk.checksum_sha256,
            "source": "knowledge_layer",
        }

        if doc:
            metadata["tenant_id"] = doc.tenant_id
            metadata["document_type"] = doc.document_type
            metadata["title"] = doc.title
            if doc.metadata:
                if doc.metadata.domain:
                    metadata["domain"] = doc.metadata.domain
                if doc.metadata.action_class:
                    metadata["action_class"] = doc.metadata.action_class
                if doc.metadata.phase_label:
                    metadata["phase_label"] = doc.metadata.phase_label
                if doc.metadata.tags:
                    metadata["tags"] = doc.metadata.tags
                if doc.metadata.event_date:
                    metadata["event_date"] = doc.metadata.event_date

        # Merge chunk-level metadata
        if kl_chunk.metadata:
            metadata["chunk_metadata"] = kl_chunk.metadata

        if snapshot:
            metadata["snapshot_id"] = snapshot.snapshot_id
            metadata["ontology_version"] = snapshot.ontology_version
            metadata["calibration_model_version"] = snapshot.calibration_model_version

        return DocumentChunk(
            chunk_id=f"kl_{kl_chunk.document_id}_{kl_chunk.chunk_id}",
            text=kl_chunk.content,
            topic=topic,
            doc_type=doc_type or "",
            metadata=metadata,
        )

    def _document_to_synthetic_chunk(
        self,
        doc: DocumentRead,
        version_number: Optional[int] = None,
        checksum: Optional[str] = None,
        snapshot: Optional[SnapshotRead] = None,
    ) -> DocumentChunk:
        """
        Fallback: create a synthetic chunk from document title and metadata.

        Used when no KL-managed chunks exist for a document version.
        """
        topic = _map_topic(doc.document_type, doc.metadata)

        # Build text from available info
        text_parts = [doc.title]
        if doc.document_type:
            text_parts.append(f"Document type: {doc.document_type}")
        if doc.metadata:
            if doc.metadata.domain:
                text_parts.append(f"Domain: {doc.metadata.domain}")
            if doc.metadata.action_class:
                text_parts.append(f"Action: {doc.metadata.action_class}")
        text = ". ".join(text_parts)

        metadata: Dict[str, Any] = {
            "kl_document_id": doc.id,
            "tenant_id": doc.tenant_id,
            "document_type": doc.document_type,
            "created_at": doc.created_at,
            "source": "knowledge_layer",
            "synthetic_chunk": True,
        }

        if version_number is not None:
            metadata["version_number"] = version_number
        if checksum:
            metadata["checksum_sha256"] = checksum

        if doc.metadata:
            if doc.metadata.domain:
                metadata["domain"] = doc.metadata.domain
            if doc.metadata.action_class:
                metadata["action_class"] = doc.metadata.action_class
            if doc.metadata.phase_label:
                metadata["phase_label"] = doc.metadata.phase_label
            if doc.metadata.tags:
                metadata["tags"] = doc.metadata.tags

        if snapshot:
            metadata["snapshot_id"] = snapshot.snapshot_id
            metadata["ontology_version"] = snapshot.ontology_version
            metadata["calibration_model_version"] = snapshot.calibration_model_version

        return DocumentChunk(
            chunk_id=f"kl_{doc.id}",
            text=text,
            topic=topic,
            doc_type=doc.document_type or "",
            metadata=metadata,
        )
