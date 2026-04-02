"""
Knowledge Object Schemas — Manithy v1
======================================

Dataclass definitions for the four Knowledge Layer object types that HPVD
retrieves and returns as ``KnowledgeCandidate`` items.  Pattern follows the
existing ``j_file_schemas.py`` style (``to_dict()`` / ``from_dict()``).

Object types
------------
    - PolicyObject          — eligibility & compliance rules
    - ProductObject         — loan/product constraints
    - RuleMappingObject     — V1/V3 field mapper
    - DocumentSchema        — document field structure

``KnowledgeCandidate`` is the unified output envelope that wraps any of the
above objects in J14 candidates.

Design rules (hpvd_specs.mdc Section 10):
    - Every candidate must have ``type`` and ``provenance``.
    - ``rule_mapping`` is always returned (mandatory).
    - HPVD must not mutate ``observed_data``.
    - Output is deterministic: same input → same candidates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


@dataclass
class Provenance:
    """Source tracing for any knowledge object.

    Attributes:
        source: Identifier of the data source (e.g. ``"bank_internal_policy"``).
        created_at: ISO date string when the object was authored (optional).
        version: Object version string (optional).
    """

    source: str
    created_at: Optional[str] = None
    version: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"source": self.source}
        if self.created_at is not None:
            d["created_at"] = self.created_at
        if self.version is not None:
            d["version"] = self.version
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Provenance":
        return cls(
            source=data.get("source", "unknown"),
            created_at=data.get("created_at"),
            version=data.get("version"),
        )


# ---------------------------------------------------------------------------
# 2.1 PolicyObject
# ---------------------------------------------------------------------------


@dataclass
class PolicyObject:
    """Eligibility and compliance rules for a sector/product type.

    Example (banking / sme_loan)::

        PolicyObject(
            policy_id="POLICY_SME_LOAN_V1",
            sector="banking",
            eligibility_rules={"min_age": 21, "min_income": 3_000_000},
            compliance_rules={"must_have_npwp": True},
            required_documents=["loan_application_form", "identity_document"],
            provenance=Provenance(source="bank_internal_policy"),
        )
    """

    policy_id: str
    sector: str
    provenance: Provenance
    product_type: Optional[str] = None
    version: Optional[str] = None
    eligibility_rules: Dict[str, Any] = field(default_factory=dict)
    compliance_rules: Dict[str, Any] = field(default_factory=dict)
    required_documents: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "sector": self.sector,
            "product_type": self.product_type,
            "version": self.version,
            "eligibility_rules": dict(self.eligibility_rules),
            "compliance_rules": dict(self.compliance_rules),
            "required_documents": list(self.required_documents),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PolicyObject":
        prov_raw = data.get("provenance", {"source": "unknown"})
        prov = Provenance.from_dict(prov_raw) if isinstance(prov_raw, dict) else prov_raw
        return cls(
            policy_id=data["policy_id"],
            sector=data["sector"],
            provenance=prov,
            product_type=data.get("product_type"),
            version=data.get("version"),
            eligibility_rules=dict(data.get("eligibility_rules", {})),
            compliance_rules=dict(data.get("compliance_rules", {})),
            required_documents=list(data.get("required_documents", [])),
        )


# ---------------------------------------------------------------------------
# 2.2 ProductObject
# ---------------------------------------------------------------------------


@dataclass
class ProductObject:
    """Loan / product constraints and financial rules.

    Example (banking / sme_loan_standard)::

        ProductObject(
            product_id="SME_LOAN_STANDARD",
            sector="banking",
            loan_constraints={"min_amount": 5_000_000, "max_amount": 500_000_000},
            financial_rules={"max_installment_to_income_ratio": 0.4},
            provenance=Provenance(source="product_catalog"),
        )
    """

    product_id: str
    sector: str
    provenance: Provenance
    product_type: Optional[str] = None
    loan_constraints: Dict[str, Any] = field(default_factory=dict)
    financial_rules: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "sector": self.sector,
            "product_type": self.product_type,
            "loan_constraints": dict(self.loan_constraints),
            "financial_rules": dict(self.financial_rules),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProductObject":
        prov_raw = data.get("provenance", {"source": "unknown"})
        prov = Provenance.from_dict(prov_raw) if isinstance(prov_raw, dict) else prov_raw
        return cls(
            product_id=data["product_id"],
            sector=data["sector"],
            provenance=prov,
            product_type=data.get("product_type"),
            loan_constraints=dict(data.get("loan_constraints", {})),
            financial_rules=dict(data.get("financial_rules", {})),
        )


# ---------------------------------------------------------------------------
# 2.3 RuleMappingObject
# ---------------------------------------------------------------------------


@dataclass
class RuleMappingObject:
    """Mapper between observed_state fields and Core V1/V3 requirements.

    ``v1_required_fields``: fields that must be present for V1 (Coverage) to
    return COVERED.

    ``v3_required_fields``: fields needed for V3 (Decision) evaluation.

    ``document_requirements``: mapping from doc_type to availability field
    name (used by VectorState builder).

    ``consistency_rules``: list of rule assertion dicts (e.g.
    ``{"rule": "claim_amount <= guarantee_amount"}``).
    """

    mapping_id: str
    sector: str
    provenance: Provenance
    v1_required_fields: List[str] = field(default_factory=list)
    v3_required_fields: List[str] = field(default_factory=list)
    document_requirements: Dict[str, Any] = field(default_factory=dict)
    consistency_rules: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "sector": self.sector,
            "v1_required_fields": list(self.v1_required_fields),
            "v3_required_fields": list(self.v3_required_fields),
            "document_requirements": dict(self.document_requirements),
            "consistency_rules": list(self.consistency_rules),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleMappingObject":
        prov_raw = data.get("provenance", {"source": "unknown"})
        prov = Provenance.from_dict(prov_raw) if isinstance(prov_raw, dict) else prov_raw
        return cls(
            mapping_id=data["mapping_id"],
            sector=data["sector"],
            provenance=prov,
            v1_required_fields=list(data.get("v1_required_fields", [])),
            v3_required_fields=list(data.get("v3_required_fields", [])),
            document_requirements=dict(data.get("document_requirements", {})),
            consistency_rules=list(data.get("consistency_rules", [])),
        )


# ---------------------------------------------------------------------------
# 2.4 DocumentSchema
# ---------------------------------------------------------------------------


@dataclass
class DocumentSchema:
    """Expected field structure for a document type.

    Used by Parser (field availability) and HPVD (document requirement
    validation).
    """

    doc_type: str
    provenance: Provenance
    sector: Optional[str] = None
    fields: List[str] = field(default_factory=list)
    required: List[str] = field(default_factory=list)
    derived_fields: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doc_type": self.doc_type,
            "sector": self.sector,
            "fields": list(self.fields),
            "required": list(self.required),
            "derived_fields": list(self.derived_fields),
            "provenance": self.provenance.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentSchema":
        prov_raw = data.get("provenance", {"source": "unknown"})
        prov = Provenance.from_dict(prov_raw) if isinstance(prov_raw, dict) else prov_raw
        return cls(
            doc_type=data["doc_type"],
            provenance=prov,
            sector=data.get("sector"),
            fields=list(data.get("fields", [])),
            required=list(data.get("required", [])),
            derived_fields=list(data.get("derived_fields", [])),
        )


# ---------------------------------------------------------------------------
# KnowledgeCandidate — unified output envelope
# ---------------------------------------------------------------------------

KnowledgeCandidateType = Literal["policy", "product", "rule_mapping", "document_schema"]


@dataclass
class KnowledgeCandidate:
    """Unified output envelope for a single knowledge object retrieved by HPVD.

    Shape required by hpvd_specs.mdc Section 10::

        {
          "type": "policy" | "product" | "rule_mapping" | "document_schema",
          "data": { ...full knowledge object... },
          "provenance": { "source": "...", "created_at": "..." }
        }

    ``data`` is stored as a raw dict so that ``KnowledgeCandidate`` remains
    schema-agnostic — callers can deserialize via the appropriate
    ``XxxObject.from_dict()`` if needed.
    """

    type: KnowledgeCandidateType
    data: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": dict(self.data),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "KnowledgeCandidate":
        if "type" not in raw:
            raise ValueError("KnowledgeCandidate missing required field: 'type'")
        if "provenance" not in raw:
            raise ValueError("KnowledgeCandidate missing required field: 'provenance'")
        return cls(
            type=raw["type"],
            data=dict(raw.get("data", {})),
            provenance=dict(raw["provenance"]),
        )

    # ------------------------------------------------------------------
    # Convenience typed-object accessors
    # ------------------------------------------------------------------

    def as_policy(self) -> PolicyObject:
        """Deserialize ``data`` into a ``PolicyObject``."""
        if self.type != "policy":
            raise TypeError(f"Expected type 'policy', got '{self.type}'")
        return PolicyObject.from_dict({**self.data, "provenance": self.provenance})

    def as_product(self) -> ProductObject:
        """Deserialize ``data`` into a ``ProductObject``."""
        if self.type != "product":
            raise TypeError(f"Expected type 'product', got '{self.type}'")
        return ProductObject.from_dict({**self.data, "provenance": self.provenance})

    def as_rule_mapping(self) -> RuleMappingObject:
        """Deserialize ``data`` into a ``RuleMappingObject``."""
        if self.type != "rule_mapping":
            raise TypeError(f"Expected type 'rule_mapping', got '{self.type}'")
        return RuleMappingObject.from_dict({**self.data, "provenance": self.provenance})

    def as_document_schema(self) -> DocumentSchema:
        """Deserialize ``data`` into a ``DocumentSchema``."""
        if self.type != "document_schema":
            raise TypeError(f"Expected type 'document_schema', got '{self.type}'")
        return DocumentSchema.from_dict({**self.data, "provenance": self.provenance})
