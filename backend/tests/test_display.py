from app.display import format_leaderboard
from app.models.scoring import Leaderboard, LeaderboardEntry


def test_format_leaderboard_matches_box_shape():
    leaderboard = Leaderboard(
        round_number=1,
        weights={"accuracy": 0.40, "reasoning": 0.35, "utility": 0.25},
        entries=[
            LeaderboardEntry(
                rank=1, agent_id="scientist", personality_name="Scientist",
                judge_score=9.1, avg_accuracy=9.5, avg_reasoning=9.0, avg_utility=8.5, score=9.1,
            ),
            LeaderboardEntry(
                rank=2, agent_id="minimalist", personality_name="Minimalist",
                judge_score=5.7, avg_accuracy=6.0, avg_reasoning=5.5, avg_utility=5.5, score=5.7,
            ),
        ],
    )

    table = format_leaderboard(leaderboard)
    lines = table.splitlines()

    assert lines[0].startswith("╭") and lines[0].endswith("╮")
    assert lines[-1].startswith("╰") and lines[-1].endswith("╯")
    assert "Agent" in lines[1]
    assert "Score" in lines[1]
    assert "Scientist" in table
    assert "9.1" in table
    assert "Minimalist" in table
    assert "5.7" in table
    # Rank 1 (Scientist, higher score) must appear before rank 2.
    assert table.index("Scientist") < table.index("Minimalist")


def test_format_leaderboard_handles_empty_entries():
    leaderboard = Leaderboard(round_number=1, weights={"accuracy": 1.0, "reasoning": 0.0, "utility": 0.0}, entries=[])
    assert format_leaderboard(leaderboard) == "(no entries to rank)"