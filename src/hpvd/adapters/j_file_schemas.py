"""
J-File Schemas — J13 through J16
=================================

Dataclass definitions following the ``HPVD_Output`` serialization pattern
(``to_dict()`` / ``from_dict()``).

Naming convention: ``manithy.<name>.v<N>``
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# J13 — Post-Core Query
# ---------------------------------------------------------------------------

@dataclass
class J13_PostCoreQuery:
    """
    Inbound query envelope routed to the retrieval layer.

    Attributes:
        schema_id: Schema identifier (``manithy.post_core_query.v2``).
        query_id: Unique query identifier.
        scope: Domain and action class (e.g. ``{"domain": "knowledge", "action_class": "loan_application"}``).
        allowed_topics: Restrict retrieval to these topics / regimes (finance/document domains).
        allowed_corpora: Restrict to named corpora (finance/document domains).
        allowed_doc_types: Optional doc-type filter (document domain).
        query_payload: Domain-specific payload (HPVDInputBundle fields for finance, text for document).
        observed_data: Observed fields from Parser output (knowledge domain — Manithy v1).
        sector: Sector identifier from Parser metadata (knowledge domain — Manithy v1).
    """

    query_id: str
    scope: Dict[str, str]
    allowed_topics: List[str] = field(default_factory=list)
    allowed_corpora: List[str] = field(default_factory=list)
    allowed_doc_types: List[str] = field(default_factory=list)
    query_payload: Dict[str, Any] = field(default_factory=dict)
    observed_data: Dict[str, Any] = field(default_factory=dict)
    sector: str = ""
    schema_id: str = "manithy.post_core_query.v2"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "query_id": self.query_id,
            "scope": dict(self.scope),
            "allowed_topics": list(self.allowed_topics),
            "allowed_corpora": list(self.allowed_corpora),
            "allowed_doc_types": list(self.allowed_doc_types),
            "query_payload": dict(self.query_payload),
            "observed_data": dict(self.observed_data),
            "sector": self.sector,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "J13_PostCoreQuery":
        for key in ("query_id", "scope"):
            if key not in data:
                raise ValueError(f"J13_PostCoreQuery missing required key: {key}")
        return cls(
            schema_id=data.get("schema_id", "manithy.post_core_query.v2"),
            query_id=data["query_id"],
            scope=dict(data["scope"]),
            allowed_topics=list(data.get("allowed_topics", [])),
            allowed_corpora=list(data.get("allowed_corpora", [])),
            allowed_doc_types=list(data.get("allowed_doc_types", [])),
            query_payload=dict(data.get("query_payload", {})),
            observed_data=dict(data.get("observed_data", {})),
            sector=str(data.get("sector", "")),
        )


# ---------------------------------------------------------------------------
# J14 — Retrieval Raw
# ---------------------------------------------------------------------------

@dataclass
class J14_RetrievalRaw:
    """
    Raw retrieval results before any phase filtering.

    Attributes:
        schema_id: ``manithy.hpvd_retrieval_raw.v1``
        query_id: Originating query ID.
        domain: Domain that produced the candidates.
        candidates: Serialized ``RetrievalCandidate`` dicts.
        diagnostics: Strategy-specific diagnostics.
    """

    query_id: str
    domain: str
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    schema_id: str = "manithy.hpvd_retrieval_raw.v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "query_id": self.query_id,
            "domain": self.domain,
            "candidates": list(self.candidates),
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "J14_RetrievalRaw":
        for key in ("query_id", "domain"):
            if key not in data:
                raise ValueError(f"J14_RetrievalRaw missing required key: {key}")
        return cls(
            schema_id=data.get("schema_id", "manithy.hpvd_retrieval_raw.v1"),
            query_id=data["query_id"],
            domain=data["domain"],
            candidates=list(data.get("candidates", [])),
            diagnostics=dict(data.get("diagnostics", {})),
        )


# ---------------------------------------------------------------------------
# J15 — Phase-Filtered Set
# ---------------------------------------------------------------------------

@dataclass
class J15_PhaseFilteredSet:
    """
    Candidates split into accepted / rejected by a phase (topic/regime) filter.

    Attributes:
        schema_id: ``manithy.phase_filtered_set.v1``
        query_id: Originating query ID.
        accepted: Candidates that passed the filter.
        rejected: Candidates that did not pass.
        filter_criteria: Description of the applied filter.
    """

    query_id: str
    accepted: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Dict[str, Any]] = field(default_factory=list)
    filter_criteria: Dict[str, Any] = field(default_factory=dict)
    schema_id: str = "manithy.phase_filtered_set.v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "query_id": self.query_id,
            "accepted": list(self.accepted),
            "rejected": list(self.rejected),
            "filter_criteria": dict(self.filter_criteria),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "J15_PhaseFilteredSet":
        if "query_id" not in data:
            raise ValueError("J15_PhaseFilteredSet missing required key: query_id")
        return cls(
            schema_id=data.get("schema_id", "manithy.phase_filtered_set.v1"),
            query_id=data["query_id"],
            accepted=list(data.get("accepted", [])),
            rejected=list(data.get("rejected", [])),
            filter_criteria=dict(data.get("filter_criteria", {})),
        )


# ---------------------------------------------------------------------------
# J16 — Analog Family Assignment
# ---------------------------------------------------------------------------

@dataclass
class J16_AnalogFamilyAssignment:
    """
    Final family assignment output.

    Attributes:
        schema_id: ``manithy.analog_family_assignment.v1``
        query_id: Originating query ID.
        families: Serialized ``FamilyAssignment`` dicts.
        total_members: Sum of all family sizes.
        total_families: Number of families.
        metadata: Arbitrary metadata.
    """

    query_id: str
    families: List[Dict[str, Any]] = field(default_factory=list)
    total_members: int = 0
    total_families: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    schema_id: str = "manithy.analog_family_assignment.v1"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "query_id": self.query_id,
            "families": list(self.families),
            "total_members": self.total_members,
            "total_families": self.total_families,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "J16_AnalogFamilyAssignment":
        if "query_id" not in data:
            raise ValueError("J16_AnalogFamilyAssignment missing required key: query_id")
        return cls(
            schema_id=data.get("schema_id", "manithy.analog_family_assignment.v1"),
            query_id=data["query_id"],
            families=list(data.get("families", [])),
            total_members=int(data.get("total_members", 0)),
            total_families=int(data.get("total_families", 0)),
            metadata=dict(data.get("metadata", {})),
        )
