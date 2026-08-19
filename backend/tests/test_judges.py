import json

import pytest
import respx
from httpx import Response

from app.judges import AccuracyJudge, ReasoningJudge, UtilityJudge, build_judges, rank_by_overall
from app.models.judge import AnonymizedAnswer
from app.ollama_manager import OllamaManager

HOST = "http://ollama.test"

ANSWERS = [
    AnonymizedAnswer(letter="A", answer="TCP backs off using additive increase, multiplicative decrease."),
    AnonymizedAnswer(letter="B", answer="Congestion control just means the router gets faster."),
]

VALID_JSON = json.dumps(
    [
        {"answer_id": "A", "accuracy": 9, "reasoning": 8, "utility": 7, "overall": 8.0, "critique": "Correct and clear."},
        {"answer_id": "B", "accuracy": 2, "reasoning": 3, "utility": 2, "overall": 2.3, "critique": "Factually wrong."},
    ]
)


@pytest.fixture
def manager():
    return OllamaManager(host=HOST, timeout=5)


def test_three_judges_have_distinct_names_and_focus(manager):
    judges = build_judges(model="qwen2.5:7b", manager=manager)
    names = {j.name for j in judges}
    focuses = {j.focus for j in judges}

    assert names == {"Accuracy Judge", "Reasoning Judge", "Utility Judge"}
    assert len(focuses) == 3  # all different


def test_system_prompt_mentions_own_focus(manager):
    judge = AccuracyJudge(model="qwen2.5:7b", manager=manager)
    prompt = judge.build_system_prompt()
    assert "accuracy" in prompt.lower()
    assert "JSON" in prompt


@respx.mock
async def test_evaluate_parses_clean_json_array(manager):
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": VALID_JSON}))

    judge = AccuracyJudge(model="qwen2.5:7b", manager=manager)
    result = await judge.evaluate("Explain TCP congestion control.", ANSWERS)

    assert result.judge_name == "Accuracy Judge"
    assert len(result.scores) == 2
    a_score = next(s for s in result.scores if s.answer_id == "A")
    assert a_score.accuracy == 9
    assert a_score.overall == 8.0


@respx.mock
async def test_evaluate_handles_markdown_fenced_json(manager):
    fenced = f"Here is my evaluation:\n```json\n{VALID_JSON}\n```"
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": fenced}))

    judge = ReasoningJudge(model="qwen2.5:7b", manager=manager)
    result = await judge.evaluate("Explain TCP congestion control.", ANSWERS)

    assert len(result.scores) == 2


@respx.mock
async def test_evaluate_raises_on_unparseable_response(manager):
    respx.post(f"{HOST}/api/generate").mock(
        return_value=Response(200, json={"response": "I refuse to output JSON today."})
    )

    judge = UtilityJudge(model="qwen2.5:7b", manager=manager)
    with pytest.raises(ValueError):
        await judge.evaluate("Explain TCP congestion control.", ANSWERS)


@respx.mock
async def test_evaluate_skips_scores_for_unknown_answer_ids(manager):
    payload = json.dumps(
        [
            {"answer_id": "A", "accuracy": 9, "reasoning": 8, "utility": 7, "overall": 8.0, "critique": "ok"},
            {"answer_id": "Z", "accuracy": 5, "reasoning": 5, "utility": 5, "overall": 5.0, "critique": "phantom answer"},
        ]
    )
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": payload}))

    judge = AccuracyJudge(model="qwen2.5:7b", manager=manager)
    result = await judge.evaluate("Explain TCP congestion control.", ANSWERS)

    assert len(result.scores) == 1
    assert result.scores[0].answer_id == "A"


@respx.mock
async def test_rank_by_overall_sorts_descending(manager):
    respx.post(f"{HOST}/api/generate").mock(return_value=Response(200, json={"response": VALID_JSON}))

    judge = AccuracyJudge(model="qwen2.5:7b", manager=manager)
    result = await judge.evaluate("Explain TCP congestion control.", ANSWERS)

    ranking = rank_by_overall(result)
    assert ranking == [("A", 8.0), ("B", 2.3)]