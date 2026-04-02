"""
Strategy Dispatcher
===================

Routes a ``J13_PostCoreQuery`` to the correct ``RetrievalStrategy``
based on the domain declared in ``j13.scope["domain"]``.

Domain aliases allow convenience names (e.g. ``"chatbot"`` → ``"document"``).
"""

from typing import Dict, Optional

from .j_file_schemas import J13_PostCoreQuery
from .retrieval_strategy import RetrievalStrategy


# Canonical aliases — maps convenience names to strategy domain keys.
DOMAIN_ALIASES: Dict[str, str] = {
    # Finance family (capital markets / OHLCV market data)
    "finance": "finance",
    "equity": "finance",
    # Knowledge family (Manithy v1 — sector-agnostic knowledge retrieval)
    # Use scope.domain = "knowledge" explicitly to route to KnowledgeRetrievalStrategy.
    "knowledge": "knowledge",
    # Document family (full-text document retrieval)
    "document": "document",
    "chatbot": "document",
    "refund": "document",
    # "banking" and "loan" kept as document aliases for backward compatibility.
    # New code should use domain="knowledge" for sector-agnostic Knowledge Layer retrieval.
    "banking": "document",
    "loan": "document",
}


class StrategyDispatcher:
    """
    Registry + dispatcher for ``RetrievalStrategy`` instances.

    Usage::

        dispatcher = StrategyDispatcher()
        dispatcher.register(FinanceRetrievalStrategy(HPVDConfig()))
        dispatcher.register(DocumentRetrievalStrategy())
        strategy = dispatcher.dispatch(j13)
    """

    def __init__(self) -> None:
        self._strategies: Dict[str, RetrievalStrategy] = {}

    def register(self, strategy: RetrievalStrategy) -> None:
        """Register a strategy under its canonical ``domain`` name."""
        self._strategies[strategy.domain] = strategy

    def dispatch(self, j13: J13_PostCoreQuery) -> RetrievalStrategy:
        """
        Resolve the strategy for *j13*.

        Raises ``ValueError`` if the domain (after alias resolution) is
        not registered.
        """
        raw_domain = j13.scope.get("domain", "")
        canonical = DOMAIN_ALIASES.get(raw_domain.lower(), raw_domain.lower())

        strategy = self._strategies.get(canonical)
        if strategy is None:
            registered = sorted(self._strategies.keys())
            raise ValueError(
                f"No strategy registered for domain {raw_domain!r} "
                f"(resolved to {canonical!r}). "
                f"Registered domains: {registered}"
            )
        return strategy

    @property
    def registered_domains(self) -> list:
        """Return sorted list of registered canonical domain names."""
        return sorted(self._strategies.keys())
