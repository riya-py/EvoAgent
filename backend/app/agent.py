"""
Agent — Phase 3.

Goal per the spec: before creating 8 agents, make ONE agent work
perfectly.

Flow:
    Question -> Personality -> System Prompt -> Ollama -> Answer

An Agent pairs one Personality with one concrete (already-resolved)
Ollama model name. It knows nothing about judges, scoring, or other
agents — that starts in Phase 4/5. It also keeps its own call history
so `.statistics` can be read at any time.
"""
from __future__ import annotations

import logging

from app.models.agent import AgentAnswer, AgentStatistics
from app.models.personality import Personality
from app.ollama_manager import OllamaManager, ollama_manager

logger = logging.getLogger(__name__)

# Per the spec: agents return conclusions and concise explanations, not
# their private chain-of-thought. Appended to every personality's own
# system_prompt so this behavior is consistent across all agents.
RESPONSE_GUARDRAIL = (
    "Respond with your conclusion and a concise supporting explanation. "
    "Do not reveal step-by-step private reasoning or chain-of-thought. "
    "Write in natural, flowing prose like you're talking to someone — "
    "not a formatted report. Avoid markdown headers, bold labels, or "
    "bullet-point breakdowns unless a list is genuinely the clearest way "
    "to say something. No '**What's established**' or '**Key points**' "
    "style section headers, ever."
)


class Agent:
    def __init__(self, personality: Personality, model: str, manager: OllamaManager | None = None):
        self.personality = personality
        self.model = model
        self.manager = manager or ollama_manager
        self.history: list[AgentAnswer] = []

    @property
    def agent_id(self) -> str:
        return self.personality.id

    def build_system_prompt(self) -> str:
        return f"{self.personality.system_prompt}\n\n{RESPONSE_GUARDRAIL}"

    async def answer(self, question: str) -> AgentAnswer:
        result = await self.manager.generate(
            model=self.model,
            prompt=question,
            system=self.build_system_prompt(),
        )

        agent_answer = AgentAnswer(
            agent_id=self.agent_id,
            personality_name=self.personality.name,
            model=self.model,
            question=question,
            answer=result.response,
            success=result.success,
            generation_time_ms=result.response_time_ms,
            error=result.error,
        )
        self.history.append(agent_answer)

        if not result.success:
            logger.warning("Agent %s failed to answer: %s", self.agent_id, result.error)

        return agent_answer

    @property
    def statistics(self) -> AgentStatistics:
        total = len(self.history)
        successes = [a for a in self.history if a.success]
        success_count = len(successes)
        avg_time = (
            sum(a.generation_time_ms for a in self.history) / total if total else 0.0
        )
        return AgentStatistics(
            agent_id=self.agent_id,
            total_calls=total,
            success_count=success_count,
            failure_count=total - success_count,
            avg_generation_time_ms=avg_time,
        )

    def __repr__(self) -> str:
        return f"Agent(id={self.agent_id!r}, model={self.model!r}, calls={len(self.history)})"