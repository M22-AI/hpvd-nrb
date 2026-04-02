"""
Knowledge Retrieval Tests — Manithy v1
=======================================

Test scenarios K1–K7 (from docs/HPVD_CORE.md Section 6.1).

These tests are written BEFORE the implementation and are expected to FAIL
until KnowledgeRetrievalStrategy is implemented (Step 4c).

All 72 existing tests remain untouched.  This file adds behaviour for the
new Knowledge Layer retrieval path.

Scenarios
---------
K1  Sector match       — only objects from the requested sector returned
K2  Field match        — observed fields trigger relevant policy/product
K3  Mandatory rule_mapping — always present even if no field matches
K4  Provenance completeness — every candidate has type + provenance
K5  Empty sector       — unknown sector → empty candidates, no crash
K6  Determinism        — same input → same candidates (order + content)
K7  Pipeline integration — J13 → HPVDPipelineEngine → J14/J15/J16 works
"""

import pytest

from hpvd.adapters.knowledge_schemas import (
    DocumentSchema,
    KnowledgeCandidate,
    PolicyObject,
    ProductObject,
    Provenance,
    RuleMappingObject,
)
from hpvd.adapters.strategies.knowledge_strategy import KnowledgeRetrievalStrategy
from hpvd.adapters.pipeline_engine import HPVDPipelineEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def banking_corpus():
    """Minimal Knowledge Layer corpus for the 'banking' sector."""
    return [
        {
            "object_type": "policy",
            "policy_id": "POLICY_SME_LOAN_V1",
            "sector": "banking",
            "product_type": "sme_loan",
            "eligibility_rules": {"min_income": 3_000_000, "min_age": 21},
            "compliance_rules": {"must_not_blacklisted": True},
            "required_documents": [
                "loan_application_form",
                "identity_document",
                "bank_statement",
                "financial_statement",
            ],
            "provenance": {"source": "bank_internal_policy", "created_at": "2026-01-01"},
        },
        {
            "object_type": "product",
            "product_id": "SME_LOAN_STANDARD",
            "sector": "banking",
            "loan_constraints": {
                "min_amount": 5_000_000,
                "max_amount": 500_000_000,
                "tenor_options": [12, 24, 36, 60],
            },
            "financial_rules": {"max_installment_to_income_ratio": 0.4},
            "provenance": {"source": "product_catalog"},
        },
        {
            "object_type": "rule_mapping",
            "mapping_id": "RULE_MAP_SME_LOAN_V1",
            "sector": "banking",
            "v1_required_fields": [
                "loan_amount",
                "loan_contract_date",
                "beneficiary_name",
            ],
            "v3_required_fields": ["loan_amount", "income", "dti_ratio"],
            "document_requirements": {
                "loan_application_form": "doc_application_present",
                "bank_statement": "doc_bank_statement_present",
            },
            "consistency_rules": [{"rule": "loan_amount <= max_amount_product"}],
            "provenance": {"source": "core_binding_definition"},
        },
    ]


@pytest.fixture()
def chatbot_corpus():
    """Minimal corpus for 'chatbot' sector (different sector from banking)."""
    return [
        {
            "object_type": "policy",
            "policy_id": "POLICY_REFUND_V1",
            "sector": "chatbot",
            "eligibility_rules": {"max_refund_amount": 5_000_000},
            "compliance_rules": {},
            "required_documents": ["payment_proof"],
            "provenance": {"source": "refund_policy"},
        },
        {
            "object_type": "rule_mapping",
            "mapping_id": "RULE_MAP_REFUND_V1",
            "sector": "chatbot",
            "v1_required_fields": ["refund_amount", "order_id"],
            "v3_required_fields": ["refund_amount", "payment_proof_present"],
            "document_requirements": {},
            "consistency_rules": [],
            "provenance": {"source": "core_binding_definition"},
        },
    ]


@pytest.fixture()
def banking_strategy(banking_corpus, chatbot_corpus):
    """A KnowledgeRetrievalStrategy loaded with banking + chatbot corpus."""
    strategy = KnowledgeRetrievalStrategy()
    strategy.build_index(banking_corpus + chatbot_corpus)
    return strategy


@pytest.fixture()
def loan_observed():
    """Observed data from a banking loan application."""
    return {
        "applicant_name": "Budi Santoso",
        "loan_amount": 50_000_000,
        "income": 10_000_000,
        "nik": "1234567890123456",
    }


# ---------------------------------------------------------------------------
# K1 — Sector match
# ---------------------------------------------------------------------------


def test_k1_sector_filter_returns_only_matching_sector(banking_strategy, loan_observed):
    """K1: querying 'banking' sector must not return chatbot objects."""
    result = banking_strategy.search(
        {"observed_data": loan_observed, "sector": "banking"}, k=25
    )
    for cand_dict in result.candidates:
        # candidates are RetrievalCandidate; metadata carries sector info
        assert cand_dict.metadata.get("sector") == "banking", (
            f"Candidate with sector {cand_dict.metadata.get('sector')} leaked into banking result"
        )


# ---------------------------------------------------------------------------
# K2 — Field-based match
# ---------------------------------------------------------------------------


def test_k2_field_based_match_returns_relevant_policy(banking_strategy, loan_observed):
    """K2: observed fields 'loan_amount' and 'income' → SME loan policy retrieved."""
    result = banking_strategy.search(
        {"observed_data": loan_observed, "sector": "banking"}, k=25
    )
    types_returned = {c.metadata.get("knowledge_type") for c in result.candidates}
    assert "policy" in types_returned, "Policy not returned for loan_amount + income observation"
    assert "product" in types_returned, "Product not returned for loan_amount + income observation"


# ---------------------------------------------------------------------------
# K3 — Mandatory rule_mapping
# ---------------------------------------------------------------------------


def test_k3_mandatory_rule_mapping_always_returned(banking_strategy):
    """K3: rule_mapping is always returned even when observed_data is empty."""
    result = banking_strategy.search(
        {"observed_data": {}, "sector": "banking"}, k=25
    )
    types_returned = {c.metadata.get("knowledge_type") for c in result.candidates}
    assert "rule_mapping" in types_returned, (
        "rule_mapping must always be included (mandatory per spec)"
    )


# ---------------------------------------------------------------------------
# K4 — Provenance completeness
# ---------------------------------------------------------------------------


def test_k4_all_candidates_have_type_and_provenance(banking_strategy, loan_observed):
    """K4: every candidate in J14 must carry 'knowledge_type' and 'provenance'."""
    result = banking_strategy.search(
        {"observed_data": loan_observed, "sector": "banking"}, k=25
    )
    assert result.candidates, "Expected at least one candidate"
    for cand in result.candidates:
        assert "knowledge_type" in cand.metadata, (
            f"Candidate {cand.candidate_id!r} missing 'knowledge_type' in metadata"
        )
        assert "provenance" in cand.metadata, (
            f"Candidate {cand.candidate_id!r} missing 'provenance' in metadata"
        )
        assert cand.metadata["provenance"].get("source"), (
            f"Candidate {cand.candidate_id!r} has empty provenance.source"
        )


# ---------------------------------------------------------------------------
# K5 — Empty / unknown sector
# ---------------------------------------------------------------------------


def test_k5_unknown_sector_returns_empty_candidates_no_crash(banking_strategy):
    """K5: querying an unknown sector returns empty list, does not raise."""
    result = banking_strategy.search(
        {"observed_data": {"amount": 1000}, "sector": "unknown_sector_xyz"}, k=25
    )
    assert result.candidates == [], (
        "Unknown sector should return empty candidates list"
    )


# ---------------------------------------------------------------------------
# K6 — Determinism
# ---------------------------------------------------------------------------


def test_k6_same_input_same_output(banking_strategy, loan_observed):
    """K6: calling search twice with identical input produces identical results."""
    query = {"observed_data": loan_observed, "sector": "banking"}
    result1 = banking_strategy.search(query, k=25)
    result2 = banking_strategy.search(query, k=25)

    ids1 = [c.candidate_id for c in result1.candidates]
    ids2 = [c.candidate_id for c in result2.candidates]
    assert ids1 == ids2, "Determinism violated: candidate IDs differ between two identical calls"


# ---------------------------------------------------------------------------
# K7 — Pipeline integration
# ---------------------------------------------------------------------------


def test_k7_pipeline_engine_end_to_end(banking_corpus, chatbot_corpus, loan_observed):
    """K7: J13 → HPVDPipelineEngine → J14/J15/J16 with KnowledgeRetrievalStrategy."""
    strategy = KnowledgeRetrievalStrategy()
    strategy.build_index(banking_corpus + chatbot_corpus)

    pipeline = HPVDPipelineEngine()
    pipeline.register_strategy(strategy)

    j13_dict = {
        "query_id": "TEST_K7_001",
        "scope": {"domain": "knowledge"},
        "observed_data": loan_observed,
        "sector": "banking",
    }

    output = pipeline.process_query(j13_dict)

    # J14 — raw candidates present
    assert output.j14.query_id == "TEST_K7_001"
    assert output.j14.domain == "knowledge"
    assert len(output.j14.candidates) > 0, "J14 must contain at least one candidate"

    # J15 — accepted candidates present
    assert output.j15.query_id == "TEST_K7_001"
    assert len(output.j15.accepted) > 0, "J15 must have accepted candidates"

    # J16 — families present
    assert output.j16.query_id == "TEST_K7_001"
    assert output.j16.total_families > 0, "J16 must contain at least one knowledge family"

    # Mandatory: rule_mapping must appear somewhere in J14 candidates
    j14_types = {c.get("knowledge_type") for c in output.j14.candidates}
    assert "rule_mapping" in j14_types, "rule_mapping must be in J14 candidates"


# ---------------------------------------------------------------------------
# Schema unit tests (knowledge_schemas.py)
# ---------------------------------------------------------------------------


def test_knowledge_candidate_roundtrip():
    """KnowledgeCandidate to_dict / from_dict roundtrip."""
    cand = KnowledgeCandidate(
        type="policy",
        data={"policy_id": "P1", "sector": "banking"},
        provenance={"source": "bank_policy"},
    )
    restored = KnowledgeCandidate.from_dict(cand.to_dict())
    assert restored.type == "policy"
    assert restored.data["policy_id"] == "P1"
    assert restored.provenance["source"] == "bank_policy"


def test_knowledge_candidate_missing_type_raises():
    """from_dict without 'type' must raise ValueError."""
    with pytest.raises(ValueError, match="type"):
        KnowledgeCandidate.from_dict({"data": {}, "provenance": {"source": "x"}})


def test_knowledge_candidate_missing_provenance_raises():
    """from_dict without 'provenance' must raise ValueError."""
    with pytest.raises(ValueError, match="provenance"):
        KnowledgeCandidate.from_dict({"type": "policy", "data": {}})


def test_policy_object_roundtrip():
    """PolicyObject to_dict / from_dict roundtrip."""
    obj = PolicyObject(
        policy_id="P1",
        sector="banking",
        eligibility_rules={"min_income": 3_000_000},
        compliance_rules={},
        required_documents=["id_doc"],
        provenance=Provenance(source="test"),
    )
    restored = PolicyObject.from_dict(obj.to_dict())
    assert restored.policy_id == "P1"
    assert restored.eligibility_rules["min_income"] == 3_000_000


def test_rule_mapping_object_roundtrip():
    """RuleMappingObject to_dict / from_dict roundtrip."""
    obj = RuleMappingObject(
        mapping_id="RM1",
        sector="banking",
        v1_required_fields=["loan_amount", "income"],
        v3_required_fields=["dti_ratio"],
        document_requirements={"bank_statement": "doc_bs_present"},
        consistency_rules=[{"rule": "a <= b"}],
        provenance=Provenance(source="core_binding"),
    )
    restored = RuleMappingObject.from_dict(obj.to_dict())
    assert restored.mapping_id == "RM1"
    assert "loan_amount" in restored.v1_required_fields


def test_knowledge_strategy_domain():
    """KnowledgeRetrievalStrategy.domain must equal 'knowledge'."""
    strategy = KnowledgeRetrievalStrategy()
    assert strategy.domain == "knowledge"
