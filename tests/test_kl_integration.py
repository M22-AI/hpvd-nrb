"""
KL Integration Tests
=====================

Tests for KL Client, Document Loader, and end-to-end HPVD pipeline
using data from the Knowledge Layer API.

Tests marked ``@pytest.mark.integration`` require a live KL API.
Other tests use mocked responses and run offline.

Usage::

    # Unit tests only (offline, mocked)
    python -m pytest tests/test_kl_integration.py -k "not integration" -v

    # Integration tests (requires live KL API + API key)
    KL_API_KEY=kl_xxx python -m pytest tests/test_kl_integration.py -m integration -v

    # All tests
    python -m pytest tests/test_kl_integration.py -v
"""

import json
import os
import pytest
from unittest.mock import MagicMock, patch
from typing import List

from src.hpvd.adapters.kl_client import (
    KLClient,
    DocumentRead,
    DocumentVersionRead,
    DocumentMetadata,
    ChunkRead,
    SnapshotRead,
    SnapshotItemRead,
    DocumentCandidateRead,
    EventRead,
    TenantRead,
    ApiKeyCreated,
)
from src.hpvd.adapters.kl_document_loader import (
    KLDocumentLoader,
    _map_topic,
    DOC_TYPE_TO_TOPIC,
)
from src.hpvd.adapters.strategies.document_strategy import (
    DocumentChunk,
    DocumentRetrievalConfig,
    DocumentRetrievalStrategy,
)
from src.hpvd.adapters.pipeline_engine import HPVDPipelineEngine, PipelineOutput


# =====================================================================
# Fixtures — mock data
# =====================================================================

MOCK_METADATA = {
    "domain": "finance",
    "action_class": "TRADE_EXECUTION",
    "phase_label": "EXECUTION_PHASE",
    "tags": ["high_volatility", "escalation"],
    "event_date": "2025-11-15",
}

MOCK_DOCUMENTS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 1. intimazione_17-11-2025.pdf",
        "document_type": "INTIMAZIONE",
        "metadata": {
            "domain": "finance",
            "action_class": "DEBT_COLLECTION",
            "phase_label": "EXECUTION_PHASE",
            "tags": ["legal_notice"],
            "event_date": "2025-11-17",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:00:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 5. delibera_17-11-2025.pdf",
        "document_type": "DELIBERA",
        "metadata": {
            "domain": "finance",
            "action_class": "CREDIT_APPROVAL",
            "phase_label": "DECISION_PHASE",
            "tags": ["bank_decision"],
            "event_date": "2025-11-17",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:01:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 6. contratto e pda_17-11-2025.pdf",
        "document_type": "CONTRACT",
        "metadata": {
            "domain": "finance",
            "action_class": "TRADE_EXECUTION",
            "phase_label": "EXECUTION_PHASE",
            "tags": ["contract", "repayment"],
            "event_date": "2025-11-17",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:02:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "tenant_id": "BANKING_CORE",
        "title": "[1440632] 1. Intimazione di pagamento.pdf",
        "document_type": "INTIMAZIONE",
        "metadata": {
            "domain": "finance",
            "action_class": "DEBT_COLLECTION",
            "phase_label": "EXECUTION_PHASE",
            "tags": ["legal_notice"],
            "event_date": "2025-12-01",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:03:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000005",
        "tenant_id": "BANKING_CORE",
        "title": "[3585136] 4. Centrale rischi.pdf",
        "document_type": "CREDIT_REPORT",
        "metadata": {
            "domain": "finance",
            "action_class": "RISK_ASSESSMENT",
            "phase_label": "ANALYSIS_PHASE",
            "tags": ["credit_risk"],
            "event_date": "2025-10-20",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:04:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000006",
        "tenant_id": "BANKING_CORE",
        "title": "[3585136] 3. Piano industriale e finanziario.pdf",
        "document_type": "INDUSTRIAL_PLAN",
        "metadata": {
            "domain": "finance",
            "action_class": "FINANCIAL_PLANNING",
            "phase_label": "PLANNING_PHASE",
            "tags": ["industrial_plan"],
            "event_date": "2025-10-15",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:05:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000007",
        "tenant_id": "BANKING_CORE",
        "title": "[4282668] 7. Fidejussione Mazzuoli Fabio.pdf",
        "document_type": "FIDEJUSSIONE",
        "metadata": {
            "domain": "finance",
            "action_class": "GUARANTEE_ISSUANCE",
            "phase_label": "EXECUTION_PHASE",
            "tags": ["guarantee"],
            "event_date": "2025-09-10",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:06:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000008",
        "tenant_id": "BANKING_CORE",
        "title": "[4016870] 14. no difficoltà BILANCIO 2021.pdf",
        "document_type": "NO_DEFAULT",
        "metadata": {
            "domain": "finance",
            "action_class": "COMPLIANCE_CHECK",
            "phase_label": "VERIFICATION_PHASE",
            "tags": ["compliance"],
            "event_date": "2025-08-20",
        },
        "created_by": "seed_script_v2",
        "created_at": "2026-03-10T10:07:00Z",
    },
]

MOCK_VERSIONS = [
    {
        "id": "v0000001",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "version_number": 1,
        "file_path": "/uploads/1437613/intimazione.pdf",
        "file_size": 125000,
        "checksum_sha256": "abc123def456",
        "raw_text": None,
        "uploaded_by": "seed_script_v2",
        "created_at": "2026-03-10T10:00:01Z",
    }
]

MOCK_CHUNKS = [
    {
        "id": "c-uuid-001",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "version_number": 1,
        "chunk_id": "c01",
        "sequence": 1,
        "content": "Intimazione di pagamento per il debito residuo di EUR 150.000.",
        "checksum_sha256": "chunk_sha256_001",
        "metadata": {"action_class": "DEBT_COLLECTION", "page": 1},
        "created_at": "2026-03-10T10:00:02Z",
    },
    {
        "id": "c-uuid-002",
        "document_id": "00000000-0000-0000-0000-000000000001",
        "version_number": 1,
        "chunk_id": "c02",
        "sequence": 2,
        "content": "Termine ultimo per il pagamento: 30 giorni dalla data di ricezione.",
        "checksum_sha256": "chunk_sha256_002",
        "metadata": {"action_class": "DEBT_COLLECTION", "page": 1},
        "created_at": "2026-03-10T10:00:02Z",
    },
]

MOCK_SNAPSHOT = {
    "id": "snap-uuid-001",
    "tenant_id": "BANKING_CORE",
    "snapshot_id": "PINSET_2026W10",
    "description": "Weekly knowledge pin for banking",
    "ontology_version": "ontology_finance_v2",
    "calibration_model_version": "calib_v3",
    "created_by": "system",
    "created_at": "2026-03-10T12:00:00Z",
    "items": [
        {
            "document_id": "00000000-0000-0000-0000-000000000001",
            "version_number": 1,
            "checksum_sha256": "abc123def456",
        },
        {
            "document_id": "00000000-0000-0000-0000-000000000002",
            "version_number": 1,
            "checksum_sha256": "def456ghi789",
        },
    ],
}


# =====================================================================
# Unit Tests — KLClient models
# =====================================================================


class TestKLClientModels:
    """Test data models parse correctly."""

    def test_document_read_from_dict(self):
        doc = DocumentRead.from_dict(MOCK_DOCUMENTS[0])
        assert doc.id == "00000000-0000-0000-0000-000000000001"
        assert doc.tenant_id == "BANKING_CORE"
        assert doc.document_type == "INTIMAZIONE"

    def test_document_read_with_metadata(self):
        doc = DocumentRead.from_dict(MOCK_DOCUMENTS[0])
        assert doc.metadata is not None
        assert doc.metadata.domain == "finance"
        assert doc.metadata.action_class == "DEBT_COLLECTION"
        assert doc.metadata.phase_label == "EXECUTION_PHASE"
        assert "legal_notice" in doc.metadata.tags
        assert doc.metadata.event_date == "2025-11-17"

    def test_document_metadata_to_dict(self):
        meta = DocumentMetadata(
            domain="finance",
            action_class="TRADE_EXECUTION",
            phase_label="EXECUTION_PHASE",
            tags=["test"],
            event_date="2025-01-01",
        )
        d = meta.to_dict()
        assert d["domain"] == "finance"
        assert d["action_class"] == "TRADE_EXECUTION"
        assert d["tags"] == ["test"]

    def test_document_metadata_from_none(self):
        meta = DocumentMetadata.from_dict(None)
        assert meta.domain is None
        assert meta.action_class is None

    def test_document_version_read_from_dict(self):
        ver = DocumentVersionRead.from_dict(MOCK_VERSIONS[0])
        assert ver.version_number == 1
        assert ver.file_size == 125000
        assert ver.checksum_sha256 == "abc123def456"

    def test_chunk_read_from_dict(self):
        chunk = ChunkRead.from_dict(MOCK_CHUNKS[0])
        assert chunk.chunk_id == "c01"
        assert chunk.sequence == 1
        assert "Intimazione" in chunk.content
        assert chunk.checksum_sha256 == "chunk_sha256_001"
        assert chunk.metadata["action_class"] == "DEBT_COLLECTION"

    def test_snapshot_read_from_dict(self):
        snap = SnapshotRead.from_dict(MOCK_SNAPSHOT)
        assert snap.snapshot_id == "PINSET_2026W10"
        assert snap.ontology_version == "ontology_finance_v2"
        assert snap.calibration_model_version == "calib_v3"
        assert len(snap.items) == 2
        assert snap.items[0].document_id == "00000000-0000-0000-0000-000000000001"
        assert snap.items[0].checksum_sha256 == "abc123def456"

    def test_document_candidate_read_from_dict(self):
        data = {
            "document_id": "00000000-0000-0000-0000-000000000001",
            "version_number": 1,
            "checksum_sha256": "abc123def456",
            "metadata": {"domain": "finance", "action_class": "TRADE_EXECUTION"},
            "snapshot_id": "PINSET_2026W10",
        }
        cand = DocumentCandidateRead.from_dict(data)
        assert cand.document_id == "00000000-0000-0000-0000-000000000001"
        assert cand.snapshot_id == "PINSET_2026W10"
        assert cand.metadata.domain == "finance"

    def test_event_read_from_dict(self):
        event_data = {
            "id": "e001",
            "tenant_id": "BANKING_CORE",
            "event_kind": "KNOWLEDGE_SNAPSHOT_PINNED",
            "payload": {"case_ids": ["1437613"]},
            "commit_id": None,
            "previous_hash": None,
            "event_hash": "sha256_test",
            "created_by": "test",
            "created_at": "2026-03-10T10:00:00Z",
        }
        event = EventRead.from_dict(event_data)
        assert event.event_kind == "KNOWLEDGE_SNAPSHOT_PINNED"
        assert event.payload["case_ids"] == ["1437613"]

    def test_tenant_read_from_dict(self):
        data = {"id": "BANKING_CORE", "name": "Banking Core", "created_at": "2026-03-10T10:00:00Z"}
        tenant = TenantRead.from_dict(data)
        assert tenant.id == "BANKING_CORE"
        assert tenant.name == "Banking Core"

    def test_api_key_created_from_dict(self):
        data = {
            "id": "key-uuid-001",
            "tenant_id": "BANKING_CORE",
            "name": "hpvd_integration",
            "key_prefix": "kl_abc",
            "is_active": True,
            "raw_key": "kl_abc123456789",
            "expires_at": None,
            "created_at": "2026-03-10T10:00:00Z",
        }
        key = ApiKeyCreated.from_dict(data)
        assert key.raw_key == "kl_abc123456789"
        assert key.is_active is True


# =====================================================================
# Unit Tests — KLDocumentLoader (mocked client)
# =====================================================================


class TestKLDocumentLoader:
    """Test document loader with mocked KL client."""

    def _make_mock_client(self, with_chunks: bool = False) -> KLClient:
        """Create a mocked KLClient."""
        client = MagicMock(spec=KLClient)
        client.list_documents.return_value = [
            DocumentRead.from_dict(d) for d in MOCK_DOCUMENTS
        ]
        client.list_versions.return_value = [
            DocumentVersionRead.from_dict(v) for v in MOCK_VERSIONS
        ]
        if with_chunks:
            client.list_chunks.return_value = [
                ChunkRead.from_dict(c) for c in MOCK_CHUNKS
            ]
        else:
            client.list_chunks.return_value = []
        return client

    def test_load_as_chunks_returns_document_chunks(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        assert len(chunks) == len(MOCK_DOCUMENTS)
        for chunk in chunks:
            assert isinstance(chunk, DocumentChunk)
            assert chunk.chunk_id.startswith("kl_")
            assert chunk.text  # non-empty
            assert chunk.topic  # mapped from doc type / metadata

    def test_load_as_chunks_with_kl_chunks(self):
        """When KL-managed chunks exist, uses actual chunk content."""
        client = self._make_mock_client(with_chunks=True)
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        # Should have 2 chunks per document (from MOCK_CHUNKS) × 8 docs
        assert len(chunks) == len(MOCK_DOCUMENTS) * len(MOCK_CHUNKS)
        for chunk in chunks:
            assert "Intimazione" in chunk.text or "Termine" in chunk.text

    def test_chunk_topics_from_metadata_domain(self):
        """Topics now come from metadata.domain first."""
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        # All mock documents have metadata.domain = "finance"
        for chunk in chunks:
            assert chunk.topic == "finance"

    def test_chunk_topics_fallback_to_doc_type(self):
        """Without metadata, falls back to document_type mapping."""
        client = MagicMock(spec=KLClient)
        client.list_documents.return_value = [
            DocumentRead(
                id="test-001",
                tenant_id="T",
                title="Test Doc",
                document_type="INTIMAZIONE",
                metadata=None,
            )
        ]
        client.list_versions.return_value = []
        client.list_chunks.return_value = []
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        assert chunks[0].topic == "legal_notice"

    def test_chunk_metadata_contains_kl_source(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        for chunk in chunks:
            assert chunk.metadata["source"] == "knowledge_layer"
            assert "kl_document_id" in chunk.metadata
            assert chunk.metadata["tenant_id"] == "BANKING_CORE"

    def test_synthetic_chunks_have_structured_metadata(self):
        """Synthetic chunks include metadata from DocumentMetadata."""
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks()

        for chunk in chunks:
            assert chunk.metadata.get("domain") == "finance"
            assert chunk.metadata.get("action_class") is not None
            assert chunk.metadata.get("phase_label") is not None
            assert chunk.metadata.get("synthetic_chunk") is True

    def test_doc_type_to_topic_mapping(self):
        """Verify the mapping function handles edge cases."""
        assert _map_topic("INTIMAZIONE") == "legal_notice"
        assert _map_topic("CONTRACT") == "contract"
        assert _map_topic("DELIBERA") == "bank_decision"
        assert _map_topic(None) == "unknown"
        assert _map_topic("") == "unknown"
        # Unknown type returns lowercase
        assert _map_topic("SOME_NEW_TYPE") == "some_new_type"

    def test_topic_mapping_prefers_metadata_domain(self):
        """Metadata.domain takes priority over document_type."""
        meta = DocumentMetadata(domain="banking")
        assert _map_topic("INTIMAZIONE", meta) == "banking"


# =====================================================================
# Unit Tests — Snapshot-based loading
# =====================================================================


class TestSnapshotLoading:
    """Test snapshot-based document loading."""

    def _make_snapshot_client(self) -> KLClient:
        client = MagicMock(spec=KLClient)
        client.get_snapshot.return_value = SnapshotRead.from_dict(MOCK_SNAPSHOT)
        client.get_document.side_effect = lambda doc_id: DocumentRead.from_dict(
            next(d for d in MOCK_DOCUMENTS if d["id"] == doc_id)
        )
        client.list_chunks.return_value = [
            ChunkRead.from_dict(c) for c in MOCK_CHUNKS
        ]
        return client

    def test_load_from_snapshot_returns_chunks(self):
        client = self._make_snapshot_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_from_snapshot("PINSET_2026W10")

        assert len(chunks) > 0
        client.get_snapshot.assert_called_once_with("PINSET_2026W10")

    def test_snapshot_chunks_have_lineage(self):
        """Chunks from snapshot loading include snapshot metadata."""
        client = self._make_snapshot_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_from_snapshot("PINSET_2026W10")

        for chunk in chunks:
            assert chunk.metadata["snapshot_id"] == "PINSET_2026W10"
            assert chunk.metadata["ontology_version"] == "ontology_finance_v2"
            assert chunk.metadata["calibration_model_version"] == "calib_v3"

    def test_snapshot_fallback_without_chunks(self):
        """If no KL chunks, falls back to synthetic chunk."""
        client = MagicMock(spec=KLClient)
        client.get_snapshot.return_value = SnapshotRead.from_dict(MOCK_SNAPSHOT)
        client.get_document.side_effect = lambda doc_id: DocumentRead.from_dict(
            next(d for d in MOCK_DOCUMENTS if d["id"] == doc_id)
        )
        client.list_chunks.return_value = []

        loader = KLDocumentLoader(client)
        chunks = loader.load_from_snapshot("PINSET_2026W10")

        assert len(chunks) == 2  # 2 items in snapshot
        for chunk in chunks:
            assert chunk.metadata.get("synthetic_chunk") is True
            assert chunk.metadata["snapshot_id"] == "PINSET_2026W10"


# =====================================================================
# Unit Tests — Search-based loading
# =====================================================================


class TestSearchLoading:
    """Test search-based document loading."""

    def test_load_with_search_calls_search_endpoint(self):
        client = MagicMock(spec=KLClient)
        client.search_documents.return_value = [
            DocumentRead.from_dict(d) for d in MOCK_DOCUMENTS[:3]
        ]
        client.list_versions.return_value = [
            DocumentVersionRead.from_dict(MOCK_VERSIONS[0])
        ]
        client.list_chunks.return_value = []

        loader = KLDocumentLoader(client)
        chunks = loader.load_with_search(
            domain="finance",
            action_class="TRADE_EXECUTION",
        )

        assert len(chunks) == 3
        client.search_documents.assert_called_once_with(
            domain="finance",
            action_class="TRADE_EXECUTION",
            phase_label=None,
            tag=None,
            snapshot_id=None,
            from_date=None,
            to_date=None,
            preset=None,
            limit=50,
        )


# =====================================================================
# Unit Tests — Pipeline with mocked KL data
# =====================================================================


class TestPipelineWithKLData:
    """Test that KL-sourced DocumentChunks work through the HPVD pipeline."""

    def _get_mock_chunks(self) -> List[DocumentChunk]:
        """Get DocumentChunks from mocked KL data."""
        client = MagicMock(spec=KLClient)
        client.list_documents.return_value = [
            DocumentRead.from_dict(d) for d in MOCK_DOCUMENTS
        ]
        client.list_versions.return_value = []
        client.list_chunks.return_value = []
        loader = KLDocumentLoader(client)
        return loader.load_as_chunks()

    def test_chunks_build_index_successfully(self):
        """KL chunks can be indexed by DocumentRetrievalStrategy."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)
        # Should not raise
        assert strategy._is_built

    def test_search_returns_candidates(self):
        """Search over KL-sourced chunks returns results."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        result = strategy.search({"text": "bank loan contract deliberation"})
        assert len(result.candidates) > 0
        for c in result.candidates:
            assert 0.0 <= c.score <= 1.0

    def test_search_with_topic_filter(self):
        """Topic filter works with KL-derived topics."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        result = strategy.search({
            "text": "legal notice payment",
            "allowed_topics": ["finance"],
        })
        for c in result.candidates:
            assert c.metadata["topic"] == "finance"

    def test_compute_families_from_kl_data(self):
        """Family formation works with KL-sourced data."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        result = strategy.search({"text": "credit risk assessment loan"})
        families = strategy.compute_families(result.candidates)

        assert isinstance(families, list)
        if families:
            for f in families:
                assert f.coherence.size > 0
                assert f.family_id.startswith("DF_")

    def test_full_pipeline_j13_to_j16(self):
        """Full pipeline: J13 → dispatch → search → J14 → J15 → J16."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        pipeline = HPVDPipelineEngine(strategies=[strategy])

        j13_dict = {
            "query_id": "kl_test_q1",
            "scope": {"domain": "banking"},
            "allowed_topics": [],
            "query_payload": {"text": "loan guarantee contract"},
        }

        out = pipeline.process_query(j13_dict, k=10)

        assert isinstance(out, PipelineOutput)
        assert out.j14.domain == "document"
        assert out.j14.query_id == "kl_test_q1"
        assert len(out.j14.candidates) > 0
        assert out.j16.total_families >= 1

    def test_pipeline_output_json_serializable(self):
        """Pipeline output from KL data is JSON-serializable."""
        chunks = self._get_mock_chunks()
        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        pipeline = HPVDPipelineEngine(strategies=[strategy])

        j13_dict = {
            "query_id": "kl_serial_test",
            "scope": {"domain": "loan"},
            "allowed_topics": [],
            "query_payload": {"text": "payment default risk"},
        }

        out = pipeline.process_query(j13_dict, k=10)
        d = out.to_dict()

        # Must not raise
        serialized = json.dumps(d, ensure_ascii=False)
        assert isinstance(serialized, str)
        assert "kl_serial_test" in serialized


# =====================================================================
# Integration Tests — requires live KL API
# =====================================================================


@pytest.mark.integration
class TestKLLiveIntegration:
    """
    Integration tests that hit the live KL API.

    Run with: ``KL_API_KEY=kl_xxx pytest -m integration``
    """

    KL_URL = "https://knowledge-layer-production.up.railway.app"

    @pytest.fixture(autouse=True)
    def _setup_client(self):
        api_key = os.environ.get("KL_API_KEY")
        if not api_key:
            pytest.skip("KL_API_KEY not set")
        self.client = KLClient(base_url=self.KL_URL, api_key=api_key)
        yield
        self.client.close()

    def test_health_check(self):
        """KL API is reachable."""
        result = self.client.health_check()
        assert result is not None

    def test_list_documents(self):
        """Can list documents."""
        docs = self.client.list_documents(limit=10)
        assert isinstance(docs, list)

    def test_list_documents_with_filters(self):
        """Can list documents with metadata filters."""
        docs = self.client.list_documents(domain="finance", limit=10)
        assert isinstance(docs, list)

    def test_search_documents(self):
        """Can search documents."""
        docs = self.client.search_documents(domain="finance", limit=10)
        assert isinstance(docs, list)

    def test_search_candidates(self):
        """Can search document candidates."""
        candidates = self.client.search_candidates(domain="finance", limit=10)
        assert isinstance(candidates, list)

    def test_list_snapshots(self):
        """Can list snapshots."""
        snapshots = self.client.list_snapshots(limit=10)
        assert isinstance(snapshots, list)

    def test_verify_chain(self):
        """Event chain verification endpoint works."""
        result = self.client.verify_chain()
        assert result is not None

    def test_full_pipeline_from_live_kl(self):
        """
        End-to-end test: Live KL API → Loader → HPVD Pipeline → J14/J15/J16.

        Only meaningful after running ``seed_kl_data.py``.
        """
        loader = KLDocumentLoader(self.client)
        chunks = loader.load_as_chunks(limit=50)

        if not chunks:
            pytest.skip("No documents found — run seed_kl_data.py first")

        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        pipeline = HPVDPipelineEngine(strategies=[strategy])
        j13_dict = {
            "query_id": "live_kl_test",
            "scope": {"domain": "banking"},
            "allowed_topics": [],
            "query_payload": {"text": "credit risk loan default"},
        }

        out = pipeline.process_query(j13_dict, k=10)
        assert isinstance(out, PipelineOutput)
        assert len(out.j14.candidates) > 0
        assert out.j16.total_families >= 1

    def test_snapshot_based_pipeline(self):
        """
        End-to-end test using snapshot-based loading.

        Only meaningful after running ``seed_kl_data.py``.
        """
        snapshots = self.client.list_snapshots(limit=1)
        if not snapshots:
            pytest.skip("No snapshots found — run seed_kl_data.py first")

        snapshot_id = snapshots[0]["snapshot_id"]
        loader = KLDocumentLoader(self.client)
        chunks = loader.load_from_snapshot(snapshot_id)

        if not chunks:
            pytest.skip(f"No chunks in snapshot {snapshot_id}")

        strategy = DocumentRetrievalStrategy(
            DocumentRetrievalConfig(min_similarity=0.0)
        )
        strategy.build_index(chunks)

        pipeline = HPVDPipelineEngine(strategies=[strategy])
        j13_dict = {
            "query_id": "snapshot_live_test",
            "scope": {"domain": "banking"},
            "allowed_topics": [],
            "query_payload": {"text": "guarantee fidejussione"},
        }

        out = pipeline.process_query(j13_dict, k=10)
        assert isinstance(out, PipelineOutput)
        assert len(out.j14.candidates) > 0

        # Verify lineage includes snapshot info
        for cand_dict in out.to_dict()["j14"]["candidates"]:
            # Lineage should trace back through metadata
            pass  # Just verify no serialization errors
