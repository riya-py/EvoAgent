"""
ArenaRepository — Phase 13.

Writes everything ArenaEngine produces to SQLite, and answers the
spec's example query almost literally:

    "What happened to the Scientist in Round 5?"
        -> repo.what_happened_to("scientist", 5)

Deliberately a thin, explicit SQL layer (no ORM) — the schema lives in
app/database.py, this module just knows how to serialize/deserialize
the Phase-8-through-12 models to/from it.
"""
from __future__ import annotations

import json
from typing import Optional

from app.database import db_cursor
from app.models.arena import RoundOutcome
from app.models.personality import Personality


class ArenaRepository:
    # ------------------------------------------------------------------
    # writes
    # ------------------------------------------------------------------
    def save_agent(self, personality: Personality, model: str = "") -> None:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO agents (id, name, description, system_prompt, specialties, weaknesses, generation, parent_agent, model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET model = excluded.model
                """,
                (
                    personality.id,
                    personality.name,
                    personality.description,
                    personality.system_prompt,
                    json.dumps(personality.specialties),
                    json.dumps(personality.weaknesses),
                    personality.generation,
                    personality.parent_agent,
                    model,
                ),
            )

    def save_agents(self, personalities_and_models: list[tuple[Personality, str]]) -> None:
        for personality, model in personalities_and_models:
            self.save_agent(personality, model)

    def save_round_outcome(self, outcome: RoundOutcome, newborn_model: str = "") -> None:
        with db_cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO rounds (round_number, question, total_time_ms) VALUES (?, ?, ?)",
                (outcome.round_number, outcome.round_result.question, outcome.round_result.total_time_ms),
            )

            for answer in outcome.round_result.answers:
                cur.execute(
                    """INSERT INTO answers (round_number, agent_id, model, answer, success, generation_time_ms, error)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        outcome.round_number,
                        answer.agent_id,
                        answer.model,
                        answer.answer,
                        int(answer.success),
                        answer.generation_time_ms,
                        answer.error,
                    ),
                )

            for judge_result in outcome.judge_results:
                for score in judge_result.scores:
                    agent_id = outcome.reveal_map.get(score.answer_id, score.answer_id)
                    cur.execute(
                        """INSERT INTO evaluations (round_number, judge_name, agent_id, accuracy, reasoning, utility, overall, critique)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            outcome.round_number,
                            judge_result.judge_name,
                            agent_id,
                            score.accuracy,
                            score.reasoning,
                            score.utility,
                            score.overall,
                            score.critique,
                        ),
                    )

            if outcome.peer_voting:
                for vote in outcome.peer_voting.votes:
                    voted_for_agent = (
                        outcome.reveal_map.get(vote.voted_for_letter) if vote.voted_for_letter else None
                    )
                    cur.execute(
                        """INSERT INTO votes (round_number, voter_agent_id, voted_for_agent_id, success, error)
                           VALUES (?, ?, ?, ?, ?)""",
                        (outcome.round_number, vote.voter_agent_id, voted_for_agent, int(vote.success), vote.error),
                    )

            if outcome.eliminated:
                e = outcome.eliminated
                cur.execute(
                    """INSERT INTO eliminations (round_number, agent_id, personality_name, final_score, reason)
                       VALUES (?, ?, ?, ?, ?)""",
                    (e.round_number, e.agent_id, e.personality_name, e.final_score, e.reason),
                )

            if outcome.newborn:
                n = outcome.newborn
                cur.execute(
                    """INSERT INTO evolutions (round_number, child_id, parent_id, name, description, system_prompt, specialties, weaknesses, generation)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        outcome.round_number,
                        n.id,
                        n.parent_agent,
                        n.name,
                        n.description,
                        n.system_prompt,
                        json.dumps(n.specialties),
                        json.dumps(n.weaknesses),
                        n.generation,
                    ),
                )

        # Register the newborn as an agent too, outside the round-data
        # transaction above but still inside the same call, so agents
        # and evolutions never disagree about whether it exists.
        if outcome.newborn:
            self.save_agent(outcome.newborn, model=newborn_model)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------
    def get_agent_record(self, agent_id: str) -> Optional[dict]:
        with db_cursor() as cur:
            cur.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
            row = cur.fetchone()
        if row is None:
            return None
        record = dict(row)
        record["specialties"] = json.loads(record["specialties"] or "[]")
        record["weaknesses"] = json.loads(record["weaknesses"] or "[]")
        return record

    def get_agent_answers(self, agent_id: str, round_number: Optional[int] = None) -> list[dict]:
        with db_cursor() as cur:
            if round_number is not None:
                cur.execute(
                    "SELECT * FROM answers WHERE agent_id = ? AND round_number = ? ORDER BY id",
                    (agent_id, round_number),
                )
            else:
                cur.execute("SELECT * FROM answers WHERE agent_id = ? ORDER BY round_number", (agent_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_agent_evaluations(self, agent_id: str, round_number: Optional[int] = None) -> list[dict]:
        with db_cursor() as cur:
            if round_number is not None:
                cur.execute(
                    "SELECT * FROM evaluations WHERE agent_id = ? AND round_number = ? ORDER BY id",
                    (agent_id, round_number),
                )
            else:
                cur.execute("SELECT * FROM evaluations WHERE agent_id = ? ORDER BY round_number", (agent_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_agent_eliminations(self, agent_id: str) -> list[dict]:
        with db_cursor() as cur:
            cur.execute("SELECT * FROM eliminations WHERE agent_id = ? ORDER BY round_number", (agent_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_agent_votes_received(self, agent_id: str, round_number: Optional[int] = None) -> list[dict]:
        with db_cursor() as cur:
            if round_number is not None:
                cur.execute(
                    "SELECT * FROM votes WHERE voted_for_agent_id = ? AND round_number = ?",
                    (agent_id, round_number),
                )
            else:
                cur.execute("SELECT * FROM votes WHERE voted_for_agent_id = ? ORDER BY round_number", (agent_id,))
            return [dict(r) for r in cur.fetchall()]

    def what_happened_to(self, agent_id: str, round_number: int) -> dict:
        """The spec's example query, answerable straight from disk."""
        eliminated = next(
            (e for e in self.get_agent_eliminations(agent_id) if e["round_number"] == round_number), None
        )
        answers = self.get_agent_answers(agent_id, round_number)
        return {
            "agent": self.get_agent_record(agent_id),
            "round_number": round_number,
            "answer": answers[0] if answers else None,
            "evaluations": self.get_agent_evaluations(agent_id, round_number),
            "votes_received": self.get_agent_votes_received(agent_id, round_number),
            "eliminated": eliminated,
        }