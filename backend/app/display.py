"""
Plain-text round display — Phase 4, extended with a leaderboard
renderer in Phase 6.

Formats a RoundResult the way the spec shows it:

    Round 1

    Scientist        -> answer
    Engineer         -> answer
    ...

And a Leaderboard as a box-drawn table:

    ╭────┬────────────────────┬───────╮
    │ #  │ Agent              │ Score │
    ├────┼────────────────────┼───────┤
    │ 1  │ Scientist          │ 9.1   │
    ╰────┴────────────────────┴───────╯
"""
from __future__ import annotations

from app.models.round import RoundResult
from app.models.scoring import Leaderboard


def format_round_table(round_result: RoundResult, preview_chars: int = 60) -> str:
    lines = [f"Round {round_result.round_number}", ""]

    name_width = max(len(a.personality_name) for a in round_result.answers) + 1

    for a in round_result.answers:
        if a.success:
            text = a.answer.replace("\n", " ").strip()
            if len(text) > preview_chars:
                text = text[: preview_chars - 1].rstrip() + "…"
        else:
            text = f"[FAILED: {a.error}]"
        lines.append(f"{a.personality_name:<{name_width}}→ {text}")

    return "\n".join(lines)


def format_leaderboard(leaderboard: Leaderboard) -> str:
    if not leaderboard.entries:
        return "(no entries to rank)"

    rank_width = max(len(str(len(leaderboard.entries))), len("#")) + 2
    name_width = max(max(len(e.personality_name) for e in leaderboard.entries), len("Agent")) + 2
    score_width = len("Score") + 2

    def hline(left: str, mid: str, right: str) -> str:
        return left + "─" * rank_width + mid + "─" * name_width + mid + "─" * score_width + right

    lines = [
        hline("╭", "┬", "╮"),
        f"│{'#':^{rank_width}}│{'Agent':^{name_width}}│{'Score':^{score_width}}│",
        hline("├", "┼", "┤"),
    ]
    for e in leaderboard.entries:
        lines.append(f"│{str(e.rank):^{rank_width}}│{e.personality_name:^{name_width}}│{f'{e.score:.1f}':^{score_width}}│")
    lines.append(hline("╰", "┴", "╯"))

    return "\n".join(lines)