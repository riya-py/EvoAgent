"""
demo_round.py — a manual preview of Phase 20 "Demo Mode".

Runs ONE full arena round through your REAL ArenaEngine, EvolutionEngine,
and DiversityChecker (no shortcuts — same classes your app/tests use),
but with Ollama's HTTP calls mocked via respx (same trick your own
tests/test_arena_engine.py already uses). That's the missing piece:
pytest asserts on data, it never prints it. This script prints it.

Drop this file in EvoAgent/backend/ (next to app/) and run:

    python demo_round.py

Requires respx (already in your requirements.txt / venv, since your
tests use it).
"""
import asyncio
import json
import re

import respx
from httpx import Response

from app.agent import Agent
from app.arena_engine import ArenaEngine
from app.config import settings
from app.diversity import DiversityChecker, EvolutionEngine
from app.display import format_elimination, format_leaderboard, format_round_table
from app.evolution_input import build_evolution_input
from app.ollama_manager import OllamaManager
from app.personalities import list_personalities

HOST = settings.ollama_host  # e.g. http://localhost:11434


def mock_responder(request):
    """Routes every mocked /api/generate call based on which system
    prompt was sent — mirrors _generic_responder in your own tests,
    but scores predictably (10 down to 3) and gives a distinct
    critique per answer so evolution has something real to read."""
    payload = json.loads(request.content)
    system = payload.get("system", "")
    prompt = payload.get("prompt", "")

    if "JSON array" in system:  # judge system prompt
        letters = re.findall(r"Answer ([A-H]):", prompt)
        scores = [
            {
                "answer_id": letter,
                "accuracy": 10 - i,
                "reasoning": 10 - i,
                "utility": 10 - i,
                "overall": float(10 - i),
                "critique": f"Feedback for {letter}.",
            }
            for i, letter in enumerate(letters)
        ]
        return Response(200, json={"response": json.dumps(scores)})

    if "Design its successor now" in prompt:  # evolution engine prompt
        draft = {
            "name": "Strategic Engineer",
            "description": "Frames answers around goals while grounding them in feasibility.",
            "system_prompt": (
                "You are the Strategic Engineer. You frame answers around goals and "
                "tradeoffs, but always check them against practical feasibility."
            ),
            "specialties": ["goal framing", "practical tradeoff analysis"],
            "weaknesses": ["can overexplain simple questions"],
        }
        return Response(200, json={"response": json.dumps(draft)})

    # otherwise: a regular agent answering the arena question
    return Response(200, json={"response": "A reasonable answer to the question."})


async def main():
    manager = OllamaManager(host=HOST)
    agents = [Agent(personality=p, model="qwen2.5:7b", manager=manager) for p in list_personalities()]

    with respx.mock:
        respx.get(f"{HOST}/api/tags").mock(
            return_value=Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        )
        respx.post(f"{HOST}/api/generate").mock(side_effect=mock_responder)

        engine = ArenaEngine(agents=agents, manager=manager)
        outcome = await engine.run_round("Explain TCP congestion control.")

        print(format_round_table(outcome.round_result))
        print()
        print(format_leaderboard(outcome.leaderboard))
        print()
        print(format_elimination(outcome.eliminated))

        # ---- Phase 10/11: evolve the eliminated agent's replacement ----
        eliminated_agent = engine.get_agent(outcome.eliminated.agent_id)
        evo_input = build_evolution_input(eliminated_agent, engine.history)
        print(
            f"\nEvolution input -> avg_score={evo_input.average_score}, "
            f"critiques={evo_input.critiques}"
        )

        evo_engine = EvolutionEngine(model="qwen2.5:7b", manager=manager)
        checker = DiversityChecker()
        new_personality = await evo_engine.evolve(evo_input)

        # Phase 11: reject/regenerate if too similar to survivors — here
        # we just report the check since the mock always returns the
        # same draft.
        survivors = [a.personality for a in engine.active_agents]
        _, similarity = checker.most_similar(new_personality, survivors)

        print("\nNEW PERSONALITY:")
        print(
            f"  id={new_personality.id} name={new_personality.name!r} "
            f"generation={new_personality.generation} parent_agent={new_personality.parent_agent!r}"
        )
        print(f"  specialties={new_personality.specialties}")
        print(f"  weaknesses={new_personality.weaknesses}")
        print(f"  (most similar survivor similarity={similarity:.2f}, threshold={checker.threshold})")


if __name__ == "__main__":
    asyncio.run(main())