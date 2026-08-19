from app.agent import Agent
from app.evolution_input import build_evolution_input
from app.models.agent import AgentAnswer
from app.models.arena import RoundOutcome
from app.models.judge import JudgeResult, JudgeScore
from app.models.round import RoundResult
from app.models.scoring import Leaderboard, LeaderboardEntry
from app.ollama_manager import OllamaManager
from app.personalities import get_personality

HOST = "http://ollama.test"


def _agent() -> Agent:
    manager = OllamaManager(host=HOST, timeout=5)
    return Agent(personality=get_personality("creative"), model="mistral:7b", manager=manager)


def _outcome(round_number: int, letter: str, agent_id: str, score: float, critique: str, question: str) -> RoundOutcome:
    round_result = RoundResult(
        round_number=round_number,
        question=question,
        answers=[
            AgentAnswer(agent_id=agent_id, personality_name="Creative", model="mistral:7b", question=question, answer="some answer")
        ],
    )
    leaderboard = Leaderboard(
        round_number=round_number,
        weights={"accuracy": 0.4, "reasoning": 0.35, "utility": 0.25},
        entries=[
            LeaderboardEntry(
                rank=1, agent_id=agent_id, personality_name="Creative",
                judge_score=score, avg_accuracy=score, avg_reasoning=score, avg_utility=score, score=score,
            )
        ],
    )
    judge_results = [
        JudgeResult(
            judge_name="Accuracy Judge",
            focus="accuracy",
            scores=[JudgeScore(answer_id=letter, accuracy=int(score), reasoning=int(score), utility=int(score), overall=score, critique=critique)],
        )
    ]
    return RoundOutcome(
        round_number=round_number,
        round_result=round_result,
        judge_results=judge_results,
        leaderboard=leaderboard,
        reveal_map={letter: agent_id},
    )


def test_build_evolution_input_aggregates_scores_and_critiques():
    agent = _agent()
    outcomes = [
        _outcome(1, "F", "creative", 8.0, "Very inventive answer.", "Design a chair."),
        _outcome(2, "C", "creative", 3.0, "Factually wrong about materials.", "Explain load-bearing structures."),
    ]

    evolution_input = build_evolution_input(agent, outcomes)

    assert evolution_input.eliminated_personality.id == "creative"
    assert evolution_input.average_score == 5.5
    assert "Very inventive answer." in evolution_input.critiques
    assert "Factually wrong about materials." in evolution_input.critiques
    assert evolution_input.successful_questions == ["Design a chair."]
    assert evolution_input.failed_questions == ["Explain load-bearing structures."]
    assert evolution_input.strengths == agent.personality.specialties
    assert evolution_input.weaknesses == agent.personality.weaknesses


def test_build_evolution_input_skips_rounds_agent_did_not_participate_in():
    agent = _agent()
    outcomes = [_outcome(1, "A", "someone_else", 9.0, "n/a", "Q1")]

    evolution_input = build_evolution_input(agent, outcomes)

    assert evolution_input.average_score == 0.0
    assert evolution_input.critiques == []
    assert evolution_input.failed_questions == []
    assert evolution_input.successful_questions == []


def test_build_evolution_input_with_no_history_at_all():
    agent = _agent()
    evolution_input = build_evolution_input(agent, [])
    assert evolution_input.average_score == 0.0