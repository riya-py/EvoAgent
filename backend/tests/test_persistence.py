import pytest

from app.database import init_db
from app.models.agent import AgentAnswer
from app.models.arena import RoundOutcome
from app.models.elimination import EliminationRecord
from app.models.judge import JudgeResult, JudgeScore
from app.models.personality import Personality
from app.models.round import RoundResult
from app.models.scoring import Leaderboard, LeaderboardEntry
from app.models.voting import PeerVote, PeerVotingResult
from app.persistence import ArenaRepository
from app.personalities import get_personality


@pytest.fixture
def repo():
    init_db()
    return ArenaRepository()


def _sample_outcome(round_number: int = 5) -> RoundOutcome:
    scientist = get_personality("scientist")
    question = "Explain TCP congestion control."

    round_result = RoundResult(
        round_number=round_number,
        question=question,
        answers=[
            AgentAnswer(
                agent_id="scientist", personality_name="Scientist", model="qwen2.5:7b",
                question=question, answer="It backs off using additive increase.", success=True,
                generation_time_ms=120.0,
            ),
            AgentAnswer(
                agent_id="minimalist", personality_name="Minimalist", model="gemma2:9b",
                question=question, answer="Slows down on drop.", success=True, generation_time_ms=80.0,
            ),
        ],
    )
    reveal_map = {"A": "scientist", "B": "minimalist"}
    judge_results = [
        JudgeResult(
            judge_name="Accuracy Judge", focus="accuracy",
            scores=[
                JudgeScore(answer_id="A", accuracy=9, reasoning=8, utility=7, overall=8.0, critique="Solid and correct."),
                JudgeScore(answer_id="B", accuracy=4, reasoning=4, utility=5, overall=4.3, critique="Too vague."),
            ],
        )
    ]
    leaderboard = Leaderboard(
        round_number=round_number,
        weights={"accuracy": 0.4, "reasoning": 0.35, "utility": 0.25},
        entries=[
            LeaderboardEntry(rank=1, agent_id="scientist", personality_name="Scientist", judge_score=8.0, avg_accuracy=9, avg_reasoning=8, avg_utility=7, score=8.0),
            LeaderboardEntry(rank=2, agent_id="minimalist", personality_name="Minimalist", judge_score=4.3, avg_accuracy=4, avg_reasoning=4, avg_utility=5, score=4.3),
        ],
    )
    peer_voting = PeerVotingResult(
        votes=[
            PeerVote(voter_agent_id="scientist", voted_for_letter="A", success=True),
            PeerVote(voter_agent_id="minimalist", voted_for_letter="A", success=True),
        ],
        vote_counts={"A": 2},
    )
    eliminated = EliminationRecord(
        agent_id="minimalist", personality_name="Minimalist", round_number=round_number,
        final_score=4.3, reason=f"Lowest score (4.3) in round {round_number}",
    )
    newborn = Personality(
        id="analytical_minimalist", name="Analytical Minimalist",
        description="Concise but fact-checked.", system_prompt="You are concise and correct.",
        specialties=["conciseness", "fact-checking"], weaknesses=["can still omit context"],
        generation=1, parent_agent="minimalist",
    )

    return RoundOutcome(
        round_number=round_number, round_result=round_result, judge_results=judge_results,
        leaderboard=leaderboard, peer_voting=peer_voting, eliminated=eliminated,
        reveal_map=reveal_map, newborn=newborn,
    )


def test_init_db_creates_all_expected_tables(repo):
    from app.database import db_cursor

    with db_cursor() as cur:
        cur.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = {row["name"] for row in cur.fetchall()}

    for expected in ["meta", "agents", "rounds", "answers", "evaluations", "votes", "eliminations", "evolutions"]:
        assert expected in tables


def test_save_agent_and_retrieve_roundtrips_json_fields(repo):
    scientist = get_personality("scientist")
    repo.save_agent(scientist, model="qwen2.5:7b")

    record = repo.get_agent_record("scientist")

    assert record["name"] == "Scientist"
    assert record["model"] == "qwen2.5:7b"
    assert record["specialties"] == scientist.specialties
    assert record["weaknesses"] == scientist.weaknesses
    assert record["generation"] == 0
    assert record["parent_agent"] is None


def test_get_agent_record_missing_returns_none(repo):
    assert repo.get_agent_record("does-not-exist") is None


def test_save_round_outcome_persists_answers(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    answers = repo.get_agent_answers("scientist", round_number=5)
    assert len(answers) == 1
    assert answers[0]["answer"] == "It backs off using additive increase."
    assert answers[0]["success"] == 1


def test_save_round_outcome_persists_evaluations_with_resolved_agent_id(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    evals = repo.get_agent_evaluations("scientist", round_number=5)
    assert len(evals) == 1
    assert evals[0]["judge_name"] == "Accuracy Judge"
    assert evals[0]["critique"] == "Solid and correct."
    assert evals[0]["agent_id"] == "scientist"  # resolved from letter "A" via reveal_map


def test_save_round_outcome_persists_votes_resolved_to_agent_ids(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    votes = repo.get_agent_votes_received("scientist", round_number=5)
    assert len(votes) == 2  # both voters voted for scientist (letter A)


def test_save_round_outcome_persists_elimination(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    eliminations = repo.get_agent_eliminations("minimalist")
    assert len(eliminations) == 1
    assert eliminations[0]["round_number"] == 5
    assert eliminations[0]["final_score"] == 4.3


def test_save_round_outcome_persists_newborn_as_agent_and_evolution_record(repo):
    from app.database import db_cursor

    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    newborn_record = repo.get_agent_record("analytical_minimalist")
    assert newborn_record is not None
    assert newborn_record["model"] == "gemma2:9b"
    assert newborn_record["parent_agent"] == "minimalist"
    assert newborn_record["generation"] == 1

    with db_cursor() as cur:
        cur.execute("SELECT * FROM evolutions WHERE child_id = ?", ("analytical_minimalist",))
        row = cur.fetchone()
    assert row is not None
    assert row["parent_id"] == "minimalist"
    assert row["round_number"] == 5


def test_what_happened_to_returns_combined_history(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_agent(get_personality("scientist"), model="qwen2.5:7b")
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    result = repo.what_happened_to("scientist", round_number=5)

    assert result["agent"]["name"] == "Scientist"
    assert result["answer"]["answer"] == "It backs off using additive increase."
    assert len(result["evaluations"]) == 1
    assert len(result["votes_received"]) == 2
    assert result["eliminated"] is None  # scientist wasn't eliminated this round


def test_what_happened_to_eliminated_agent_includes_elimination(repo):
    outcome = _sample_outcome(round_number=5)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    result = repo.what_happened_to("minimalist", round_number=5)

    assert result["eliminated"] is not None
    assert result["eliminated"]["reason"] == "Lowest score (4.3) in round 5"


def test_data_survives_a_fresh_connection(repo):
    """Persistence means it survives a restart — simulate that by just
    opening a brand new connection/cursor rather than reusing state."""
    outcome = _sample_outcome(round_number=1)
    repo.save_round_outcome(outcome, newborn_model="gemma2:9b")

    fresh_repo = ArenaRepository()  # new instance, same underlying file
    record = fresh_repo.get_agent_record("analytical_minimalist")
    assert record is not None