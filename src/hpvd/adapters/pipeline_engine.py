"""
HPVD Pipeline Engine
====================

Unified orchestrator that processes a J13 query end-to-end through the
strategy pattern, emitting J14 → J15 → J16 envelopes.

The pipeline **does not** modify HPVD core — it composes the adapter
layer on top of it.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .j_file_schemas import (
    J13_PostCoreQuery,
    J14_RetrievalRaw,
    J15_PhaseFilteredSet,
    J16_AnalogFamilyAssignment,
)
from .j13_adapter import J13Adapter
from .j14_emitter import J14Emitter
from .j15_emitter import J15Emitter
from .j16_emitter import J16Emitter
from .retrieval_strategy import RetrievalCandidate, RetrievalStrategy
from .strategy_dispatcher import StrategyDispatcher


@dataclass
class PipelineOutput:
    """
    Complete pipeline result containing all three J-file stages.

    Attributes:
        j14: Raw retrieval results.
        j15: Phase-filtered candidates.
        j16: Family assignments.
    """

    j14: J14_RetrievalRaw
    j15: J15_PhaseFilteredSet
    j16: J16_AnalogFamilyAssignment

    def to_dict(self) -> Dict[str, Any]:
        return {
            "j14": self.j14.to_dict(),
            "j15": self.j15.to_dict(),
            "j16": self.j16.to_dict(),
        }


class HPVDPipelineEngine:
    """
    Unified pipeline orchestrator.

    Usage::

        pipeline = HPVDPipelineEngine()
        pipeline.register_strategy(FinanceRetrievalStrategy(HPVDConfig()))
        pipeline.register_strategy(DocumentRetrievalStrategy())

        # Build indexes
        pipeline.build_finance_index(bundles)
        pipeline.build_document_index(chunks)

        # Run a query
        result = pipeline.process_query(j13_dict)
        assert result.j16.families
    """

    def __init__(
        self,
        strategies: Optional[List[RetrievalStrategy]] = None,
    ) -> None:
        self._dispatcher = StrategyDispatcher()
        for s in strategies or []:
            self._dispatcher.register(s)

    # ------------------------------------------------------------------
    # Registration helpers
    # ------------------------------------------------------------------

    def register_strategy(self, strategy: RetrievalStrategy) -> None:
        """Register a retrieval strategy with the dispatcher."""
        self._dispatcher.register(strategy)

    # ------------------------------------------------------------------
    # Convenience build helpers
    # ------------------------------------------------------------------

    def build_finance_index(self, bundles: Any) -> None:
        """Build the finance strategy index from ``HPVDInputBundle`` list."""
        strategy = self._dispatcher._strategies.get("finance")
        if strategy is None:
            raise RuntimeError("No finance strategy registered.")
        strategy.build_index(bundles)

    def build_document_index(self, chunks: Any) -> None:
        """Build the document strategy index from ``DocumentChunk`` list."""
        strategy = self._dispatcher._strategies.get("document")
        if strategy is None:
            raise RuntimeError("No document strategy registered.")
        strategy.build_index(chunks)

    def build_knowledge_index(self, knowledge_corpus: Any) -> None:
        """Build the knowledge strategy index from a Knowledge Layer corpus.

        Parameters
        ----------
        knowledge_corpus : list of dict
            Each dict must have an ``object_type`` key (``"policy"``,
            ``"product"``, ``"rule_mapping"``, ``"document_schema"``) and
            a ``sector`` field.  See ``KnowledgeRetrievalStrategy.build_index``
            and ``docs/HPVD_CORE.md`` Section 2 for schema details.
        """
        strategy = self._dispatcher._strategies.get("knowledge")
        if strategy is None:
            raise RuntimeError("No knowledge strategy registered.")
        strategy.build_index(knowledge_corpus)

    # ------------------------------------------------------------------
    # Main pipeline
    # ------------------------------------------------------------------

    def process_query(
        self,
        j13_dict: Dict[str, Any],
        k: int = 25,
        phase_filter_fn: Optional[Callable[[RetrievalCandidate], bool]] = None,
    ) -> PipelineOutput:
        """
        End-to-end pipeline: J13 → dispatch → search → J14 → filter → J15 → families → J16.

        Parameters
        ----------
        j13_dict : dict
            Raw J13 dict (will be parsed via ``J13_PostCoreQuery.from_dict()``).
        k : int
            Number of candidates to retrieve.
        phase_filter_fn : callable, optional
            Custom filter predicate for J15 stage.  If ``None`` a default
            pass-through filter is used (all candidates accepted).
        """
        # 1. Parse J13
        j13 = J13_PostCoreQuery.from_dict(j13_dict)

        # 2. Dispatch to strategy
        strategy = self._dispatcher.dispatch(j13)

        # 3. Adapt query
        query_dict = J13Adapter.adapt(j13)

        # 4. Search
        result = strategy.search(query_dict, k=k)

        # 5. Emit J14
        j14 = J14Emitter.emit(
            query_id=j13.query_id,
            domain=strategy.domain,
            result=result,
        )

        # 6. Phase filter → J15
        j15 = J15Emitter.emit(
            query_id=j13.query_id,
            result=result,
            filter_fn=phase_filter_fn,
            filter_criteria={
                "allowed_topics": j13.allowed_topics,
                "allowed_doc_types": j13.allowed_doc_types,
            },
        )

        # 7. Compute families → J16
        families = strategy.compute_families(result.candidates)
        j16 = J16Emitter.emit(
            query_id=j13.query_id,
            families=families,
            metadata={"domain": strategy.domain},
        )

        return PipelineOutput(j14=j14, j15=j15, j16=j16)
