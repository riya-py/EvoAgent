from app.anonymizer import anonymize_answers
from app.models.agent import AgentAnswer
from app.models.round import RoundResult


def _round_with_answers(n_success=8, n_fail=0):
    answers = []
    for i in range(n_success):
        answers.append(
            AgentAnswer(
                agent_id=f"agent-{i}",
                personality_name=f"Personality {i}",
                model="qwen2.5:7b",
                question="Q",
                answer=f"answer text {i}",
                success=True,
            )
        )
    for i in range(n_fail):
        answers.append(
            AgentAnswer(
                agent_id=f"failed-{i}",
                personality_name=f"Failed {i}",
                model="qwen2.5:7b",
                question="Q",
                success=False,
                error="boom",
            )
        )
    return RoundResult(round_number=1, question="Q", answers=answers)


def test_anonymize_assigns_sequential_letters():
    round_result = _round_with_answers(n_success=8)
    anonymized, reveal_map = anonymize_answers(round_result)

    assert [a.letter for a in anonymized] == list("ABCDEFGH")
    assert reveal_map["A"] == "agent-0"
    assert reveal_map["H"] == "agent-7"


def test_anonymized_answers_carry_no_identifying_info():
    round_result = _round_with_answers(n_success=3)
    anonymized, _ = anonymize_answers(round_result)

    for a in anonymized:
        assert not hasattr(a, "agent_id")
        assert not hasattr(a, "personality_name")
        assert not hasattr(a, "model")


def test_anonymize_skips_failed_answers():
    round_result = _round_with_answers(n_success=6, n_fail=2)
    anonymized, reveal_map = anonymize_answers(round_result)

    assert len(anonymized) == 6
    assert len(reveal_map) == 6
    assert "failed-0" not in reveal_map.values()