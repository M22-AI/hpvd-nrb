"""
J13 Adapter
============

Transforms a ``J13_PostCoreQuery`` into a strategy-specific query dict
consumable by the corresponding ``RetrievalStrategy.search()``.
"""

from typing import Any, Dict

from .j_file_schemas import J13_PostCoreQuery


class J13Adapter:
    """
    Adapts ``J13_PostCoreQuery`` into domain-specific query dicts.

    Finance  → extracts ``query_payload`` fields into bundle constructor args.
    Document → extracts ``text``, ``allowed_topics``, ``allowed_doc_types``.
    """

    @staticmethod
    def adapt(j13: J13_PostCoreQuery) -> Dict[str, Any]:
        """
        Return a strategy-ready query dict from *j13*.

        The returned dict always includes ``query_id``.  Additional keys
        depend on the domain declared in ``j13.scope["domain"]``.
        """
        domain = j13.scope.get("domain", "").lower()
        query: Dict[str, Any] = {"query_id": j13.query_id}

        if domain in ("finance", "equity"):
            # Pass the entire query_payload through — the finance strategy
            # expects either ``hpvd_input_bundle`` or raw fields (trajectory,
            # dna, geometry_context, metadata).
            query.update(j13.query_payload)
        elif domain == "knowledge":
            # Knowledge retrieval — pass observed_data and sector.
            # These fields are top-level on J13 (Manithy v1 schema).
            query["observed_data"] = j13.observed_data
            query["sector"] = j13.sector
        else:
            # Document / chatbot / banking / loan / …
            query["text"] = j13.query_payload.get("text", "")
            query["allowed_topics"] = j13.allowed_topics
            query["allowed_doc_types"] = j13.allowed_doc_types

        return query
