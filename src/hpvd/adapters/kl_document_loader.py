"""
KL Document Loader
===================

Fetches documents from the Knowledge Layer API and converts them
into ``DocumentChunk`` objects consumable by ``DocumentRetrievalStrategy``.

Since KL currently does not support:
  - Content download (G5)
  - Chunk-level storage (G2)

This loader uses document **title** and **metadata** as chunk content.
When KL adds content download support, this loader will be updated to
fetch and chunk actual file content.
"""

from typing import Any, Dict, List, Optional

from .kl_client import KLClient, DocumentRead
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


def _map_topic(document_type: Optional[str]) -> str:
    """Map a KL document_type to a topic label for HPVD."""
    if not document_type:
        return "unknown"
    return DOC_TYPE_TO_TOPIC.get(document_type.upper(), document_type.lower())


class KLDocumentLoader:
    """
    Loads documents from KL and converts to ``DocumentChunk`` list.

    Usage::

        client = KLClient()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks("BANKING_CORE")
        # → List[DocumentChunk] ready for DocumentRetrievalStrategy.build_index()
    """

    def __init__(self, client: KLClient):
        self._client = client

    def load_as_chunks(
        self,
        tenant_id: str,
        limit: int = 200,
    ) -> List[DocumentChunk]:
        """
        Fetch all documents for *tenant_id* and convert to chunks.

        Currently each document becomes **one chunk** whose text is
        built from the document title and metadata. When KL adds
        content retrieval (Gap G5), this will fetch and chunk actual
        file content.
        """
        documents = self._client.list_documents(tenant_id, limit=limit)
        chunks: List[DocumentChunk] = []

        for doc in documents:
            chunk = self._document_to_chunk(doc)
            chunks.append(chunk)

        return chunks

    def load_with_versions(
        self,
        tenant_id: str,
        limit: int = 200,
    ) -> List[DocumentChunk]:
        """
        Like ``load_as_chunks`` but also fetches version metadata,
        enriching chunk metadata with version info (checksum, file_size).
        """
        documents = self._client.list_documents(tenant_id, limit=limit)
        chunks: List[DocumentChunk] = []

        for doc in documents:
            # Fetch versions for richer metadata
            try:
                versions = self._client.list_versions(doc.id)
                latest_version = max(versions, key=lambda v: v.version_number) if versions else None
            except Exception:
                latest_version = None

            chunk = self._document_to_chunk(doc, version_info=latest_version)
            chunks.append(chunk)

        return chunks

    def _document_to_chunk(
        self,
        doc: DocumentRead,
        version_info=None,
    ) -> DocumentChunk:
        """Convert a single KL document into a ``DocumentChunk``."""
        topic = _map_topic(doc.document_type)

        # Build text content from available metadata
        # When KL adds G5 (content download), this will be replaced
        # with actual document content + chunking
        text_parts = [doc.title]
        if doc.document_type:
            text_parts.append(f"Document type: {doc.document_type}")
        if doc.created_by:
            text_parts.append(f"Created by: {doc.created_by}")
        text = ". ".join(text_parts)

        metadata: Dict[str, Any] = {
            "kl_document_id": doc.id,
            "tenant_id": doc.tenant_id,
            "document_type": doc.document_type,
            "created_at": doc.created_at,
            "source": "knowledge_layer",
        }

        if version_info is not None:
            metadata["version_number"] = version_info.version_number
            metadata["checksum_sha256"] = version_info.checksum_sha256
            metadata["file_size"] = version_info.file_size
            metadata["file_path"] = version_info.file_path

        return DocumentChunk(
            chunk_id=f"kl_{doc.id}",
            text=text,
            topic=topic,
            doc_type=doc.document_type or "",
            metadata=metadata,
        )
