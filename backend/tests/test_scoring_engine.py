import pytest

from app.models.agent import AgentAnswer
from app.models.judge import JudgeResult, JudgeScore
from app.models.round import RoundResult
from app.models.voting import PeerVote, PeerVotingResult
from app.scoring_engine import DEFAULT_WEIGHTS, ScoringEngine


def _round_result():
    answers = [
        AgentAnswer(agent_id="scientist", personality_name="Scientist", model="qwen2.5:7b", question="Q", answer="a1"),
        AgentAnswer(agent_id="creative", personality_name="Creative", model="mistral:7b", question="Q", answer="a2"),
    ]
    return RoundResult(round_number=1, question="Q", answers=answers)


def _judge_results():
    # Two judges score A and B differently so weighting actually matters.
    accuracy_judge = JudgeResult(
        judge_name="Accuracy Judge",
        focus="accuracy",
        scores=[
            JudgeScore(answer_id="A", accuracy=10, reasoning=6, utility=6, overall=8.0),
            JudgeScore(answer_id="B", accuracy=4, reasoning=6, utility=6, overall=5.0),
        ],
    )
    reasoning_judge = JudgeResult(
        judge_name="Reasoning Judge",
        focus="reasoning",
        scores=[
            JudgeScore(answer_id="A", accuracy=8, reasoning=8, utility=6, overall=7.0),
            JudgeScore(answer_id="B", accuracy=6, reasoning=9, utility=6, overall=7.0),
        ],
    )
    return [accuracy_judge, reasoning_judge]


def test_default_weights_sum_to_one_and_match_spec():
    assert DEFAULT_WEIGHTS == {"accuracy": 0.40, "reasoning": 0.35, "utility": 0.25}
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_invalid_weights_raise():
    with pytest.raises(ValueError):
        ScoringEngine(weights={"accuracy": 0.5, "reasoning": 0.5, "utility": 0.5})


def test_compute_produces_ranked_leaderboard():
    reveal_map = {"A": "scientist", "B": "creative"}
    engine = ScoringEngine()

    leaderboard = engine.compute(_judge_results(), reveal_map, _round_result())

    assert leaderboard.round_number == 1
    assert len(leaderboard.entries) == 2

    a_entry = next(e for e in leaderboard.entries if e.agent_id == "scientist")
    # avg_accuracy = (10+8)/2 = 9, avg_reasoning = (6+8)/2 = 7, avg_utility = 6
    expected = 0.40 * 9 + 0.35 * 7 + 0.25 * 6
    assert a_entry.avg_accuracy == 9.0
    assert a_entry.judge_score == round(expected, 2)
    assert a_entry.score == a_entry.judge_score  # no peer voting -> score == judge_score

    # Scientist should outrank Creative given the scores above.
    assert leaderboard.entries[0].agent_id == "scientist"
    assert leaderboard.entries[0].rank == 1
    assert leaderboard.entries[1].rank == 2


def test_custom_weights_change_ranking():
    reveal_map = {"A": "scientist", "B": "creative"}
    # Weight utility only — both answers tie at utility=6, so ranking
    # should differ from the default-weights case (still deterministic
    # but not driven by accuracy).
    engine = ScoringEngine(weights={"accuracy": 0.0, "reasoning": 0.0, "utility": 1.0})

    leaderboard = engine.compute(_judge_results(), reveal_map, _round_result())

    for entry in leaderboard.entries:
        assert entry.judge_score == entry.avg_utility


def test_missing_scores_for_an_answer_are_skipped():
    reveal_map = {"A": "scientist", "B": "creative", "C": "nonexistent"}
    engine = ScoringEngine()

    leaderboard = engine.compute(_judge_results(), reveal_map, _round_result())

    assert len(leaderboard.entries) == 2  # "C" had no judge scores at all


def test_compute_without_peer_voting_leaves_vote_fields_none():
    reveal_map = {"A": "scientist", "B": "creative"}
    engine = ScoringEngine()

    leaderboard = engine.compute(_judge_results(), reveal_map, _round_result())

    for entry in leaderboard.entries:
        assert entry.vote_score is None
        assert entry.votes_received is None
    assert leaderboard.peer_vote_weight == 0.0


def test_compute_with_peer_voting_blends_score():
    reveal_map = {"A": "scientist", "B": "creative"}
    peer_voting = PeerVotingResult(
        votes=[
            PeerVote(voter_agent_id="x", voted_for_letter="B"),
            PeerVote(voter_agent_id="y", voted_for_letter="B"),
        ],
        vote_counts={"B": 2},
    )
    engine = ScoringEngine(peer_vote_weight=0.5)

    leaderboard = engine.compute(_judge_results(), reveal_map, _round_result(), peer_voting=peer_voting)

    b_entry = next(e for e in leaderboard.entries if e.agent_id == "creative")
    a_entry = next(e for e in leaderboard.entries if e.agent_id == "scientist")

    assert b_entry.votes_received == 2
    assert b_entry.vote_score == 10.0  # got all the votes
    assert a_entry.votes_received == 0
    assert a_entry.vote_score == 0.0

    # Blended score should differ from judge_score once voting counts.
    assert b_entry.score != b_entry.judge_score
    assert b_entry.score == round(b_entry.judge_score * 0.5 + 10.0 * 0.5, 2)