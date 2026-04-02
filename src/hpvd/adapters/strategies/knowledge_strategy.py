"""
Knowledge Retrieval Strategy — Manithy v1
==========================================

Sector-agnostic knowledge retrieval strategy.  Implements the
``RetrievalStrategy`` ABC for the ``"knowledge"`` domain.

Retrieval pipeline (from HPVD_CORE.md Section 5):
    Step 1 — Sector Filter
        Retain only objects whose ``sector`` matches the requested sector.
    Step 2 — Field-Based Matching
        Extract keywords from ``observed_data``; match against policy/product
        objects that mention those fields in eligibility_rules or loan_constraints.
    Step 3 — Mandatory Retrieval
        Always include ``rule_mapping`` for the sector, regardless of field hits.
    Step 4 — Format
        Wrap each matched object as a ``KnowledgeRetrievalCandidate``.

Design rules (hpvd_specs.mdc Section 10):
    - Every candidate must carry ``knowledge_type`` and ``provenance``.
    - ``rule_mapping`` is mandatory.
    - HPVD must not modify ``observed_data``.
    - Output must be deterministic: same input → same candidates.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..retrieval_strategy import (
    FamilyAssignment,
    RetrievalCandidate,
    RetrievalResult,
    RetrievalStrategy,
)
from ...family import FamilyCoherence, StructuralSignature, UncertaintyFlags


# ---------------------------------------------------------------------------
# KnowledgeRetrievalCandidate — emits knowledge-native dict format
# ---------------------------------------------------------------------------


class KnowledgeRetrievalCandidate(RetrievalCandidate):
    """Subclass of ``RetrievalCandidate`` that emits knowledge-native dict.

    The ``to_dict()`` method promotes ``knowledge_type``, ``data``, and
    ``provenance`` to the top level so that J14 candidates have the shape
    documented in MANITHY_INTEGRATION.md Section 4:

        {
          "candidate_id": "...",
          "score": 1.0,
          "knowledge_type": "policy" | "product" | "rule_mapping" | ...,
          "sector": "banking",
          "data": { ...full knowledge object... },
          "provenance": { "source": "...", ... },
          "source_domain": "knowledge"
        }
    """

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "score": float(self.score),
            "knowledge_type": self.metadata.get("knowledge_type", ""),
            "sector": self.metadata.get("sector", ""),
            "data": dict(self.metadata.get("data", {})),
            "provenance": dict(self.metadata.get("provenance", {})),
            "source_domain": self.source_domain,
        }


# ---------------------------------------------------------------------------
# KnowledgeIndex — in-memory store keyed by sector
# ---------------------------------------------------------------------------


class KnowledgeIndex:
    """In-memory knowledge store organized by sector.

    Stores four object types:
        - ``policy``         → PolicyObject-like dicts
        - ``product``        → ProductObject-like dicts
        - ``rule_mapping``   → RuleMappingObject-like dicts
        - ``document_schema``→ DocumentSchema-like dicts

    The sector key is taken from each object's ``sector`` field.
    """

    _VALID_TYPES = {"policy", "product", "rule_mapping", "document_schema"}

    def __init__(self) -> None:
        # sector → list of (object_type, object_dict)
        self._store: Dict[str, List[tuple]] = {}

    def add(self, obj: Dict[str, Any]) -> None:
        """Insert a raw knowledge object dict into the index.

        The dict must have an ``object_type`` key (``"policy"``,
        ``"product"``, ``"rule_mapping"``, ``"document_schema"``) and a
        ``sector`` field.  Unknown object types are silently ignored.
        """
        obj_type = obj.get("object_type", "")
        if obj_type not in self._VALID_TYPES:
            return
        sector = obj.get("sector") or obj.get("doc_type", "")
        if not sector:
            return
        bucket = self._store.setdefault(sector, [])
        # Store without the ``object_type`` key — callers get it separately
        bucket.append((obj_type, {k: v for k, v in obj.items() if k != "object_type"}))

    def get_by_sector(self, sector: str) -> List[tuple]:
        """Return all (object_type, object_dict) tuples for the given sector."""
        return list(self._store.get(sector, []))

    def has_sector(self, sector: str) -> bool:
        return sector in self._store

    @property
    def sectors(self) -> List[str]:
        return sorted(self._store.keys())


# ---------------------------------------------------------------------------
# KnowledgeRetrievalStrategy
# ---------------------------------------------------------------------------


class KnowledgeRetrievalStrategy(RetrievalStrategy):
    """Retrieval strategy for the ``"knowledge"`` domain.

    Usage::

        strategy = KnowledgeRetrievalStrategy()
        strategy.build_index(corpus)          # List[dict] — knowledge objects

        result = strategy.search(
            {"observed_data": {"loan_amount": 50_000_000}, "sector": "banking"},
            k=25,
        )
        # result.candidates → List[KnowledgeRetrievalCandidate]
        # result.diagnostics → {"sector": "banking", "objects_returned": 3, ...}

        families = strategy.compute_families(result.candidates)
        # One FamilyAssignment per knowledge_type found in candidates
    """

    def __init__(self) -> None:
        self._index = KnowledgeIndex()

    # ------------------------------------------------------------------
    # RetrievalStrategy interface
    # ------------------------------------------------------------------

    @property
    def domain(self) -> str:
        return "knowledge"

    def build_index(self, corpus: Any) -> None:
        """Load knowledge objects from *corpus*.

        Parameters
        ----------
        corpus : list of dict
            Each dict must contain an ``object_type`` key
            (``"policy"``, ``"product"``, ``"rule_mapping"``,
            ``"document_schema"``) and a ``sector`` field.
        """
        self._index = KnowledgeIndex()
        for obj in corpus:
            self._index.add(obj)

    def search(self, query: Dict[str, Any], k: int = 25) -> RetrievalResult:
        """Retrieve knowledge candidates for the given query.

        Parameters
        ----------
        query : dict
            Must contain ``sector`` (str) and optionally
            ``observed_data`` (dict of field → value pairs).
        k : int
            Maximum total candidates to return (per type counts separately
            before this cap).

        Returns
        -------
        RetrievalResult
            ``candidates`` is an ordered list of
            ``KnowledgeRetrievalCandidate``.  Order: policy, product,
            rule_mapping, document_schema — deterministic within each type
            by insertion order.
        """
        sector: str = query.get("sector", "")
        observed_data: Dict[str, Any] = query.get("observed_data") or {}

        if not sector or not self._index.has_sector(sector):
            return RetrievalResult(
                candidates=[],
                diagnostics={"sector": sector, "objects_returned": 0, "sector_found": False},
                query_id=query.get("query_id", ""),
            )

        sector_objects = self._index.get_by_sector(sector)
        observed_keys = set(observed_data.keys())

        # Step 2 — Field-based scoring
        # Each object gets a relevance score: 1.0 base + 0.1 per matched field
        scored: List[tuple] = []  # (score, obj_type, obj_dict)
        rule_mapping_forced: List[tuple] = []  # always include

        for obj_type, obj_dict in sector_objects:
            if obj_type == "rule_mapping":
                rule_mapping_forced.append((1.0, obj_type, obj_dict))
                continue

            score = self._score_object(obj_type, obj_dict, observed_keys)
            scored.append((score, obj_type, obj_dict))

        # Sort by score desc, then by a stable secondary key (object id) for determinism
        scored.sort(key=lambda t: (-t[0], self._object_id(t[1], t[2])))

        # Step 3 — Build candidate list: matched objects + mandatory rule_mappings
        chosen = scored[:max(0, k - len(rule_mapping_forced))]
        all_entries = chosen + rule_mapping_forced

        candidates: List[KnowledgeRetrievalCandidate] = []
        seen_ids: set = set()
        for score_val, obj_type, obj_dict in all_entries:
            cand_id = f"{obj_type}:{self._object_id(obj_type, obj_dict)}"
            if cand_id in seen_ids:
                continue
            seen_ids.add(cand_id)
            candidates.append(
                KnowledgeRetrievalCandidate(
                    candidate_id=cand_id,
                    score=score_val,
                    metadata={
                        "knowledge_type": obj_type,
                        "sector": sector,
                        "data": dict(obj_dict),
                        "provenance": dict(obj_dict.get("provenance", {"source": "unknown"})),
                    },
                    source_domain=self.domain,
                )
            )

        return RetrievalResult(
            candidates=candidates,
            diagnostics={
                "sector": sector,
                "objects_considered": len(sector_objects),
                "objects_returned": len(candidates),
                "rule_mapping_forced": len(rule_mapping_forced) > 0,
            },
            query_id=query.get("query_id", ""),
        )

    def compute_families(
        self, candidates: List[RetrievalCandidate]
    ) -> List[FamilyAssignment]:
        """Group knowledge candidates by ``knowledge_type``.

        Returns one ``FamilyAssignment`` per distinct type found in
        *candidates*.  Family IDs follow the pattern ``knowledge_{type}``.
        """
        type_buckets: Dict[str, List[RetrievalCandidate]] = {}
        for cand in candidates:
            k_type = cand.metadata.get("knowledge_type", "unknown")
            type_buckets.setdefault(k_type, []).append(cand)

        families: List[FamilyAssignment] = []
        for k_type, members in sorted(type_buckets.items()):
            families.append(
                FamilyAssignment(
                    family_id=f"knowledge_{k_type}",
                    members=members,
                    coherence=FamilyCoherence(
                        mean_confidence=1.0,
                        dispersion=0.0,
                        size=len(members),
                    ),
                    structural_signature=StructuralSignature(
                        phase=f"{k_type}_group",
                        avg_K=None,
                        avg_LTV=None,
                        avg_LVC=None,
                    ),
                    uncertainty_flags=UncertaintyFlags(
                        phase_boundary=False,
                        weak_support=len(members) == 0,
                        partial_overlap=False,
                    ),
                )
            )
        return families

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _object_id(obj_type: str, obj: Dict[str, Any]) -> str:
        """Return the primary ID field value for *obj*, falling back to a hash."""
        id_fields = {
            "policy": "policy_id",
            "product": "product_id",
            "rule_mapping": "mapping_id",
            "document_schema": "doc_type",
        }
        field = id_fields.get(obj_type, "")
        return str(obj.get(field, id(obj)))

    @staticmethod
    def _score_object(
        obj_type: str,
        obj: Dict[str, Any],
        observed_keys: set,
    ) -> float:
        """Compute relevance score for a knowledge object.

        Base score = 1.0.  Add 0.1 for every observed field that appears
        as a key inside ``eligibility_rules`` or ``loan_constraints``.
        This keeps scoring simple and deterministic.
        """
        score = 1.0
        rule_dicts: List[Dict] = []

        if obj_type == "policy":
            rule_dicts.append(obj.get("eligibility_rules", {}))
            rule_dicts.append(obj.get("compliance_rules", {}))
        elif obj_type == "product":
            rule_dicts.append(obj.get("loan_constraints", {}))
            rule_dicts.append(obj.get("financial_rules", {}))
        elif obj_type == "document_schema":
            rule_dicts.append({f: True for f in obj.get("fields", [])})

        for rule_dict in rule_dicts:
            for key in observed_keys:
                if key in rule_dict:
                    score += 0.1

        return round(score, 6)
