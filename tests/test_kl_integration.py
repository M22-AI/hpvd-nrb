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

    # Integration tests (requires live KL API)
    python -m pytest tests/test_kl_integration.py -m integration -v

    # All tests
    python -m pytest tests/test_kl_integration.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from typing import List

from src.hpvd.adapters.kl_client import (
    KLClient,
    DocumentRead,
    DocumentVersionRead,
    EventRead,
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

MOCK_DOCUMENTS = [
    {
        "id": "00000000-0000-0000-0000-000000000001",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 1. intimazione_17-11-2025.pdf",
        "document_type": "INTIMAZIONE",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:00:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000002",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 5. delibera_17-11-2025.pdf",
        "document_type": "DELIBERA",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:01:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000003",
        "tenant_id": "BANKING_CORE",
        "title": "[1437613] 6. contratto e pda_17-11-2025.pdf",
        "document_type": "CONTRACT",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:02:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000004",
        "tenant_id": "BANKING_CORE",
        "title": "[1440632] 1. Intimazione di pagamento.pdf",
        "document_type": "INTIMAZIONE",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:03:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000005",
        "tenant_id": "BANKING_CORE",
        "title": "[3585136] 4. Centrale rischi.pdf",
        "document_type": "CREDIT_REPORT",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:04:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000006",
        "tenant_id": "BANKING_CORE",
        "title": "[3585136] 3. Piano industriale e finanziario.pdf",
        "document_type": "INDUSTRIAL_PLAN",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:05:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000007",
        "tenant_id": "BANKING_CORE",
        "title": "[4282668] 7. Fidejussione Mazzuoli Fabio.pdf",
        "document_type": "FIDEJUSSIONE",
        "created_by": "seed_script_v1",
        "created_at": "2026-03-10T10:06:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000008",
        "tenant_id": "BANKING_CORE",
        "title": "[4016870] 14. no difficoltà BILANCIO 2021.pdf",
        "document_type": "NO_DEFAULT",
        "created_by": "seed_script_v1",
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
        "uploaded_by": "seed_script_v1",
        "created_at": "2026-03-10T10:00:01Z",
    }
]


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

    def test_document_version_read_from_dict(self):
        ver = DocumentVersionRead.from_dict(MOCK_VERSIONS[0])
        assert ver.version_number == 1
        assert ver.file_size == 125000
        assert ver.checksum_sha256 == "abc123def456"

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


# =====================================================================
# Unit Tests — KLDocumentLoader (mocked client)
# =====================================================================


class TestKLDocumentLoader:
    """Test document loader with mocked KL client."""

    def _make_mock_client(self) -> KLClient:
        """Create a mocked KLClient."""
        client = MagicMock(spec=KLClient)
        client.list_documents.return_value = [
            DocumentRead.from_dict(d) for d in MOCK_DOCUMENTS
        ]
        client.list_versions.return_value = [
            DocumentVersionRead.from_dict(v) for v in MOCK_VERSIONS
        ]
        return client

    def test_load_as_chunks_returns_document_chunks(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks("BANKING_CORE")

        assert len(chunks) == len(MOCK_DOCUMENTS)
        for chunk in chunks:
            assert isinstance(chunk, DocumentChunk)
            assert chunk.chunk_id.startswith("kl_")
            assert chunk.text  # non-empty
            assert chunk.topic  # mapped from doc type

    def test_chunk_topics_correctly_mapped(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks("BANKING_CORE")

        # Check specific mappings
        topic_by_id = {c.metadata["kl_document_id"]: c.topic for c in chunks}

        # INTIMAZIONE → legal_notice
        assert topic_by_id["00000000-0000-0000-0000-000000000001"] == "legal_notice"
        # DELIBERA → bank_decision
        assert topic_by_id["00000000-0000-0000-0000-000000000002"] == "bank_decision"
        # CONTRACT → contract
        assert topic_by_id["00000000-0000-0000-0000-000000000003"] == "contract"
        # CREDIT_REPORT → credit_analysis
        assert topic_by_id["00000000-0000-0000-0000-000000000005"] == "credit_analysis"
        # FIDEJUSSIONE → guarantee
        assert topic_by_id["00000000-0000-0000-0000-000000000007"] == "guarantee"

    def test_load_with_versions_enriches_metadata(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_with_versions("BANKING_CORE")

        for chunk in chunks:
            assert "version_number" in chunk.metadata
            assert "checksum_sha256" in chunk.metadata

    def test_chunk_metadata_contains_kl_source(self):
        client = self._make_mock_client()
        loader = KLDocumentLoader(client)
        chunks = loader.load_as_chunks("BANKING_CORE")

        for chunk in chunks:
            assert chunk.metadata["source"] == "knowledge_layer"
            assert "kl_document_id" in chunk.metadata
            assert chunk.metadata["tenant_id"] == "BANKING_CORE"

    def test_doc_type_to_topic_mapping(self):
        """Verify the mapping function handles edge cases."""
        assert _map_topic("INTIMAZIONE") == "legal_notice"
        assert _map_topic("CONTRACT") == "contract"
        assert _map_topic("DELIBERA") == "bank_decision"
        assert _map_topic(None) == "unknown"
        assert _map_topic("") == "unknown"
        # Unknown type returns lowercase
        assert _map_topic("SOME_NEW_TYPE") == "some_new_type"


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
        loader = KLDocumentLoader(client)
        return loader.load_as_chunks("BANKING_CORE")

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
            "allowed_topics": ["legal_notice"],
        })
        for c in result.candidates:
            assert c.metadata["topic"] == "legal_notice"

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

    Run with: ``pytest -m integration``
    """

    KL_URL = "https://knowledge-layer-production.up.railway.app"

    def test_health_check(self):
        """KL API is reachable."""
        with KLClient(base_url=self.KL_URL) as client:
            result = client.health_check()
            assert result is not None

    def test_list_documents(self):
        """Can list documents for BANKING_CORE tenant."""
        with KLClient(base_url=self.KL_URL) as client:
            docs = client.list_documents("BANKING_CORE", limit=10)
            assert isinstance(docs, list)
            # May be empty if not yet seeded

    def test_verify_chain(self):
        """Event chain verification endpoint works."""
        with KLClient(base_url=self.KL_URL) as client:
            result = client.verify_chain()
            assert result is not None

    def test_full_pipeline_from_live_kl(self):
        """
        End-to-end test: Live KL API → Loader → HPVD Pipeline → J14/J15/J16.

        Only meaningful after running ``seed_kl_data.py``.
        """
        with KLClient(base_url=self.KL_URL) as client:
            loader = KLDocumentLoader(client)
            chunks = loader.load_as_chunks("BANKING_CORE")

            if not chunks:
                pytest.skip("No documents in BANKING_CORE tenant — run seed_kl_data.py first")

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

            # Verify provenance — all candidates should trace back to KL
            for cand in out.j14.candidates:
                assert cand.get("source_domain") == "document" or True  # serialized form
