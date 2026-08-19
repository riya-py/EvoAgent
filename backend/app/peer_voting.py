"""
Peer Voting — Phase 7.

Each agent is shown the question and the anonymized answers (minus its
own — enforced here, not just requested in the prompt, so a
non-compliant model can't self-vote) and picks the single best one.
Votes run concurrently across agents, same pattern as Phase 4's round.

Kept entirely optional: nothing in the arena calls this automatically.
It's meant to be wired in behind app.config.settings.peer_voting_enabled
starting in Phase 8, so results can be compared with and without it.
"""
from __future__ import annotations

import asyncio
import logging

from app.agent import Agent
from app.json_utils import extract_json_array
from app.models.judge import AnonymizedAnswer
from app.models.voting import PeerVote, PeerVotingResult

logger = logging.getLogger(__name__)

_VOTE_INSTRUCTIONS = """\
You are voting in a competition among anonymous answers to the same question. \
Read every answer and pick the single best one.

Respond with ONLY a JSON object in this exact shape and nothing else — no \
preamble, no markdown fences:
{"vote": "C"}
"""


def _build_vote_system_prompt() -> str:
    return _VOTE_INSTRUCTIONS


def _build_vote_user_prompt(question: str, choices: list[AnonymizedAnswer]) -> str:
    blocks = "\n\n".join(f"Answer {a.letter}:\n{a.answer}" for a in choices)
    return f"QUESTION:\n{question}\n\n{blocks}"


async def get_agent_vote(agent: Agent, question: str, choices: list[AnonymizedAnswer]) -> PeerVote:
    """`choices` must already exclude the voting agent's own answer."""
    valid_letters = {c.letter for c in choices}

    result = await agent.manager.generate(
        model=agent.model,
        prompt=_build_vote_user_prompt(question, choices),
        system=_build_vote_system_prompt(),
    )

    if not result.success:
        return PeerVote(voter_agent_id=agent.agent_id, success=False, error=result.error)

    try:
        parsed = extract_json_array(result.response)
        letter = parsed[0].get("vote")
    except (ValueError, IndexError) as exc:
        return PeerVote(voter_agent_id=agent.agent_id, success=False, error=f"unparseable vote: {exc}")

    if letter not in valid_letters:
        return PeerVote(
            voter_agent_id=agent.agent_id,
            success=False,
            error=f"voted for {letter!r}, which is not an offered (non-self) choice",
        )

    return PeerVote(voter_agent_id=agent.agent_id, voted_for_letter=letter)


async def conduct_peer_voting(
    agents: list[Agent],
    question: str,
    anonymized_answers: list[AnonymizedAnswer],
    reveal_map: dict[str, str],
) -> PeerVotingResult:
    agent_to_own_letter = {agent_id: letter for letter, agent_id in reveal_map.items()}

    async def vote_for(agent: Agent) -> PeerVote:
        own_letter = agent_to_own_letter.get(agent.agent_id)
        choices = [a for a in anonymized_answers if a.letter != own_letter]
        if not choices:
            return PeerVote(voter_agent_id=agent.agent_id, success=False, error="no other answers to vote for")
        return await get_agent_vote(agent, question, choices)

    raw_votes = await asyncio.gather(*(vote_for(agent) for agent in agents), return_exceptions=True)

    votes: list[PeerVote] = []
    for agent, v in zip(agents, raw_votes):
        if isinstance(v, Exception):
            logger.error("Agent %s failed to vote unexpectedly: %s", agent.agent_id, v)
            votes.append(PeerVote(voter_agent_id=agent.agent_id, success=False, error=str(v)))
        else:
            votes.append(v)

    vote_counts: dict[str, int] = {}
    for v in votes:
        if v.success and v.voted_for_letter:
            vote_counts[v.voted_for_letter] = vote_counts.get(v.voted_for_letter, 0) + 1

    return PeerVotingResult(votes=votes, vote_counts=vote_counts)