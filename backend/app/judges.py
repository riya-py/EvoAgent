# judge base + Accuracy/Reasoning/Utility, build_judges(), rank_by_overall()
"""
Judge System — Phase 5.

Three independent judges (Accuracy, Reasoning, Utility) each evaluate
every answer in one pass. They only ever see anonymized answers
("Answer A", "Answer B", ...) — never the personality name or model —
so personality/model bias can't creep into scoring.

Each judge scores all three dimensions (matching the JSON shape in the
spec) but its system prompt tells it which dimension to weigh most
heavily, so the three judges genuinely disagree with each other rather
than being three copies of the same evaluation.
"""
from __future__ import annotations

import logging

from pydantic import ValidationError

from app.json_utils import extract_json_array
from app.models.judge import AnonymizedAnswer, JudgeResult, JudgeScore
from app.ollama_manager import OllamaManager, ollama_manager

logger = logging.getLogger(__name__)

_JSON_SCHEMA_INSTRUCTIONS = """\
You are given a QUESTION and several anonymized ANSWERS (labeled A, B, C, ...).
Score every answer independently on three dimensions, each from 1 (worst) to \
10 (best):
  - accuracy: is it factually and technically correct?
  - reasoning: is the logic sound and well-justified?
  - utility: how practically useful/actionable is it?
Then give an "overall" score from 1 to 10 and a one-sentence "critique".

Respond with ONLY a JSON array, one object per answer, in this exact shape \
and nothing else — no preamble, no markdown fences:
[
  {"answer_id": "A", "accuracy": 8, "reasoning": 7, "utility": 9, "overall": 8.0, "critique": "..."},
  {"answer_id": "B", "accuracy": 6, "reasoning": 8, "utility": 5, "overall": 6.3, "critique": "..."}
]
"""


def _clamp_score_fields(item: dict) -> dict:
    """Force accuracy/reasoning/utility/overall back into the 1-10 range
    a model occasionally ignores (e.g. scoring something a flat 0)."""
    clamped = dict(item)
    for key in ("accuracy", "reasoning", "utility"):
        if key in clamped:
            try:
                clamped[key] = max(1, min(10, round(float(clamped[key]))))
            except (TypeError, ValueError):
                clamped[key] = 1
    if "overall" in clamped:
        try:
            clamped["overall"] = max(1.0, min(10.0, float(clamped["overall"])))
        except (TypeError, ValueError):
            clamped["overall"] = 1.0
    return clamped


class Judge:
    name: str = "Judge"
    focus: str = "overall quality"

    def __init__(self, model: str, manager: OllamaManager | None = None):
        self.model = model
        self.manager = manager or ollama_manager

    def build_system_prompt(self) -> str:
        return (
            f"You are the {self.name}, one of several independent judges scoring "
            f"AI-generated answers. Weigh {self.focus} most heavily when forming "
            f"your 'overall' score, but still score every dimension honestly.\n\n"
            f"{_JSON_SCHEMA_INSTRUCTIONS}"
        )

    def build_user_prompt(self, question: str, answers: list[AnonymizedAnswer]) -> str:
        blocks = "\n\n".join(f"Answer {a.letter}:\n{a.answer}" for a in answers)
        return f"QUESTION:\n{question}\n\n{blocks}"

    async def evaluate(self, question: str, answers: list[AnonymizedAnswer]) -> JudgeResult:
        result = await self.manager.generate(
            model=self.model,
            prompt=self.build_user_prompt(question, answers),
            system=self.build_system_prompt(),
        )

        if not result.success:
            raise ValueError(f"{self.name} generation failed: {result.error}")

        logger.info(
            "%s raw response (%d chars): %r",
            self.name, len(result.response), result.response,
        )
        raw_scores = extract_json_array(result.response)
        valid_letters = {a.letter for a in answers}

        scores: list[JudgeScore] = []
        for item in raw_scores:
            if item.get("answer_id") not in valid_letters:
                logger.warning("%s returned score for unknown answer_id %r — skipping", self.name, item.get("answer_id"))
                continue
            try:
                scores.append(JudgeScore(**item))
            except ValidationError:
                # Local/smaller models don't always obey "score 1-10" to the
                # letter (a 0, an 11, a stray string) — clamp back into range
                # rather than letting one sloppy score sink the whole round.
                clamped = _clamp_score_fields(item)
                try:
                    scores.append(JudgeScore(**clamped))
                except ValidationError as exc:
                    logger.warning(
                        "%s returned an unparseable score for %r — skipping: %s",
                        self.name, item.get("answer_id"), exc,
                    )

        return JudgeResult(judge_name=self.name, focus=self.focus, scores=scores)


class AccuracyJudge(Judge):
    name = "Accuracy Judge"
    focus = "factual and technical accuracy above all else"


class ReasoningJudge(Judge):
    name = "Reasoning Judge"
    focus = "the soundness and clarity of the reasoning/logic"


class UtilityJudge(Judge):
    name = "Utility Judge"
    focus = "how practically useful and actionable the answer is"


def build_judges(model: str, manager: OllamaManager | None = None) -> list[Judge]:
    return [
        AccuracyJudge(model=model, manager=manager),
        ReasoningJudge(model=model, manager=manager),
        UtilityJudge(model=model, manager=manager),
    ]


def rank_by_overall(judge_result: JudgeResult) -> list[tuple[str, float]]:
    """Simple descending rank by one judge's overall score. A full
    weighted, multi-judge ranking is Phase 6's ScoringEngine — this
    just proves a single judge's output can already produce a
    reliable ranking, satisfying Phase 5's done condition."""
    return sorted(((s.answer_id, s.overall) for s in judge_result.scores), key=lambda t: t[1], reverse=True)