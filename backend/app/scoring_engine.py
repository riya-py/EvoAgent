"""
ScoringEngine — Phase 6.

Combines the three independent judges' per-dimension scores into one
weighted number per answer, using the spec's default weighting:

    Accuracy   40%
    Reasoning  35%
    Utility    25%

Weights are configurable (constructor arg), and blending in a peer-vote
score (Phase 7) is entirely optional — pass a PeerVotingResult and a
non-zero peer_vote_weight to turn it on; omit both to score on judges
alone, exactly like Phase 6 runs before Phase 7 existed.
"""
from __future__ import annotations

from statistics import mean

from app.models.judge import JudgeResult
from app.models.round import RoundResult
from app.models.scoring import Leaderboard, LeaderboardEntry
from app.models.voting import PeerVotingResult

DEFAULT_WEIGHTS: dict[str, float] = {"accuracy": 0.40, "reasoning": 0.35, "utility": 0.25}


class ScoringEngine:
    def __init__(self, weights: dict[str, float] | None = None, peer_vote_weight: float = 0.0):
        self.weights = dict(weights) if weights else dict(DEFAULT_WEIGHTS)
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")
        if not (0.0 <= peer_vote_weight <= 1.0):
            raise ValueError("peer_vote_weight must be between 0.0 and 1.0")
        self.peer_vote_weight = peer_vote_weight

    def compute(
        self,
        judge_results: list[JudgeResult],
        reveal_map: dict[str, str],
        round_result: RoundResult,
        peer_voting: PeerVotingResult | None = None,
    ) -> Leaderboard:
        personality_by_agent = {a.agent_id: a.personality_name for a in round_result.answers}
        use_peer_voting = peer_voting is not None and self.peer_vote_weight > 0
        total_votes = peer_voting.total_votes_cast if peer_voting else 0

        entries: list[LeaderboardEntry] = []
        for letter, agent_id in reveal_map.items():
            scores = [s for jr in judge_results for s in jr.scores if s.answer_id == letter]
            if not scores:
                continue  # no judge scored this answer — nothing to rank

            avg_accuracy = mean(s.accuracy for s in scores)
            avg_reasoning = mean(s.reasoning for s in scores)
            avg_utility = mean(s.utility for s in scores)

            judge_score = (
                self.weights["accuracy"] * avg_accuracy
                + self.weights["reasoning"] * avg_reasoning
                + self.weights["utility"] * avg_utility
            )

            vote_score = None
            votes_received = None
            final_score = judge_score

            if use_peer_voting:
                votes_received = peer_voting.vote_counts.get(letter, 0)
                vote_score = (votes_received / total_votes * 10) if total_votes else 0.0
                final_score = judge_score * (1 - self.peer_vote_weight) + vote_score * self.peer_vote_weight

            entries.append(
                LeaderboardEntry(
                    rank=0,  # assigned below after sorting
                    agent_id=agent_id,
                    personality_name=personality_by_agent.get(agent_id, agent_id),
                    judge_score=round(judge_score, 2),
                    avg_accuracy=round(avg_accuracy, 2),
                    avg_reasoning=round(avg_reasoning, 2),
                    avg_utility=round(avg_utility, 2),
                    vote_score=round(vote_score, 2) if vote_score is not None else None,
                    votes_received=votes_received,
                    score=round(final_score, 2),
                )
            )

        entries.sort(key=lambda e: e.score, reverse=True)
        for i, entry in enumerate(entries, start=1):
            entry.rank = i

        return Leaderboard(
            round_number=round_result.round_number,
            weights=self.weights,
            peer_vote_weight=self.peer_vote_weight if use_peer_voting else 0.0,
            entries=entries,
        )