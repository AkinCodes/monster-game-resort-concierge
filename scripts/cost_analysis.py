"""LLM cost comparison across all supported models for 10-turn and 100-turn conversations."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.core.cost_tracker import MODEL_PRICING, estimate_cost  # noqa: E402


def simulate_conversation(model: str, turns: int) -> float:
    """
    Simulate a multi-turn conversation and return total cost in USD.

    Token model:
      - Turn 1 prompt: 200 tokens, growing by 40 per subsequent turn
      - Completion: 100 tokens per turn (constant)
    """
    total = 0.0
    for turn in range(turns):
        prompt_tokens = 200 + (turn * 40)
        completion_tokens = 100
        total += estimate_cost(model, prompt_tokens, completion_tokens)
    return total


def main() -> None:
    print("=" * 70)
    print("LLM COST ANALYSIS — Monster Resort Concierge")
    print("=" * 70)

    # Friendly display names (strip date suffixes for readability)
    display_names = {
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o Mini",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-3.5-turbo": "GPT-3.5 Turbo",
        "claude-sonnet-4-20250514": "Claude Sonnet 4",
        "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
        "claude-3-haiku-20240307": "Claude 3 Haiku",
        "llama3": "Llama 3 (local)",
    }

    rows = []
    for model, (input_price, output_price) in MODEL_PRICING.items():
        cost_10 = simulate_conversation(model, 10)
        cost_100 = simulate_conversation(model, 100)
        name = display_names.get(model, model)
        rows.append((name, input_price, output_price, cost_10, cost_100))

    # --- Markdown table ---
    print("\n## Cost Comparison: 10-turn and 100-turn Conversations\n")
    print("Token model: prompt starts at 200 tokens, +40/turn; completion = 100 tokens/turn.\n")

    header = "| Model | Input $/1M | Output $/1M | 10-turn cost | 100-turn cost |"
    sep =    "|-------|----------:|-----------:|-------------:|--------------:|"
    print(header)
    print(sep)

    for name, inp, out, c10, c100 in rows:
        inp_str = f"${inp:.2f}"
        out_str = f"${out:.2f}"
        c10_str = f"${c10:.6f}" if c10 > 0 else "FREE"
        c100_str = f"${c100:.6f}" if c100 > 0 else "FREE"
        print(f"| {name} | {inp_str} | {out_str} | {c10_str} | {c100_str} |")

    # --- Summary insights ---
    print("\n### Key Takeaways\n")

    cheapest_paid = min(
        ((name, c10) for name, _, _, c10, _ in rows if c10 > 0),
        key=lambda x: x[1],
    )
    most_expensive = max(rows, key=lambda x: x[3])

    print(f"- Cheapest paid model for 10 turns: **{cheapest_paid[0]}** (${cheapest_paid[1]:.6f})")
    print(f"- Most expensive for 10 turns: **{most_expensive[0]}** (${most_expensive[3]:.6f})")
    print(f"- Local Llama 3 is free but requires GPU/CPU resources")

    total_prompt = sum(200 + (t * 40) for t in range(10))
    total_completion = 100 * 10
    print(f"\n10-turn totals: {total_prompt} prompt tokens + {total_completion} completion tokens = {total_prompt + total_completion} total tokens")

    total_prompt_100 = sum(200 + (t * 40) for t in range(100))
    total_completion_100 = 100 * 100
    print(f"100-turn totals: {total_prompt_100} prompt tokens + {total_completion_100} completion tokens = {total_prompt_100 + total_completion_100} total tokens")

    print("\nDone.")


if __name__ == "__main__":
    main()
