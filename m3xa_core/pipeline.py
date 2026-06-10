"""The 7-actor query pipeline — orchestrator.

Each actor is a small, testable module under `m3xa_core/actors/`. The
pipeline runs them in sequence; see BODY.md for the actor inventory.

Self-awareness components (`m3xa_core/self_awareness/`) are *not* part of
the pipeline — they run alongside it, reading the pipeline's outputs.

Sequence:

    Query
      |
      v
    1) Classifier  ──────────────────────────►  ClassifierOutput
      |
      v
    1.5) Router    ──────────────────────────►  RoutingDecision
      |
      v
    2) Assembler  ───────► system_prompt, estimated_tokens
      |
      |       3) Agent Hub (parallel)  ───►  list[AgentContext]
      |       4) Retriever              ───►  list[RetrievedDoc]
      v
    5) Synthesizer ───────────────────────►   response (str)
      |
      v
    7) Evaluator   ───────────────────────►   EvaluationResult
      |
      v
    PipelineResult
"""
from __future__ import annotations

from pathlib import Path

from m3xa_core.actors import (
    agent_hub as agent_hub_mod,
    assembler as assembler_mod,
    classifier as classifier_mod,
    evaluator as evaluator_mod,
    retriever as retriever_mod,
    router as router_mod,
    synthesizer as synthesizer_mod,
)
from m3xa_core.schemas import (
    PipelineResult,
    SynthesizerInput,
)

DEFAULT_EXPERTISES_DIR = Path(__file__).resolve().parent.parent / "expertises"


class Pipeline:
    """Composes the 7 actors into a single callable.

    Construction takes backend objects (LLM, embeddings, vector DB) so
    each can be swapped independently — see `m3xa_core/backends/`. The
    agent hub is optional; pass `None` to run without data agents.
    """

    def __init__(
        self,
        *,
        lancedb_path: str | None = None,
        llm: object | None = None,
        embeddings: object | None = None,
        vector_db: object | None = None,
        agent_hub: agent_hub_mod.AgentHub | None = None,
        expertises_dir: Path | None = None,
    ) -> None:
        self.lancedb_path = lancedb_path
        self.llm = llm
        self.embeddings = embeddings
        self.vector_db = vector_db
        self.agent_hub = agent_hub
        self.expertises_dir = expertises_dir or DEFAULT_EXPERTISES_DIR

    def run(self, query: str) -> PipelineResult:
        """Run the 7-actor pipeline against a query.

        Returns `PipelineResult` — see `m3xa_core/schemas.py` for the shape.

        The pipeline degrades gracefully when backends are missing:
        classifier and router fall back to keyword + default-decision
        paths, retrieval returns []. The synthesizer / evaluator emit
        an informative "no LLM" string instead of raising.
        """
        # 1. Classifier
        classification = classifier_mod.classify(query, llm=self.llm)

        # 1.5 Router
        routing = router_mod.route(classification, llm=self.llm)

        # 2. Assembler — pure file ops
        system_prompt, est_tokens = assembler_mod.assemble(
            routing, expertises_dir=self.expertises_dir
        )

        # 3. Agent hub — parallel, optional
        agent_blocks = (
            self.agent_hub.fire(classification) if self.agent_hub is not None else []
        )

        # 4. Retriever
        docs = retriever_mod.retrieve(
            classification,
            embeddings=self.embeddings,
            vector_db=self.vector_db,
        )

        # 5. Synthesizer
        synth_input = SynthesizerInput(
            query=query,
            system_prompt=system_prompt,
            docs=docs,
            agent_blocks=agent_blocks,
            estimated_system_tokens=est_tokens,
        )
        response = synthesizer_mod.synthesize(synth_input, llm=self.llm)

        # 7. Evaluator
        evaluation = evaluator_mod.evaluate(query, response, llm=self.llm)

        return PipelineResult(
            query=query,
            response=response,
            score=evaluation.score,
            routing_decision=routing,
            retrieved=docs,
            estimated_system_tokens=est_tokens,
            evaluation=evaluation,
        )
