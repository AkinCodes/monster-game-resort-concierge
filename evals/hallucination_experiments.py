"""Five hallucination-detection experiments for LinkedIn article.

Each experiment probes a specific weakness in token-overlap + semantic-similarity
scoring. Run: python -m evals.hallucination_experiments
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.manager_office.hallucination import HallucinationDetector  # noqa: E402

detector = HallucinationDetector()

EXPERIMENTS = [
    # 1 ── Faithful Paraphrase (should score HIGH, will score HIGH)
    {
        "name": "The Faithful Paraphrase",
        "query": "What time is check-in?",
        "response": (
            "Check-in starts at 3 PM across most properties. "
            "If you arrive early, we can try to get your lair ready sooner. "
            "For our nocturnal friends, moonlight arrivals can be arranged."
        ),
        "contexts": [
            "Check-in is from 3:00 PM. Early check-in is available based on lair readiness.",
            "For nocturnal guests, we can arrange 'moonlight arrival' with prior notice.",
            "Checkout is by 11:00 AM. Late checkout may incur a small broomstick fee.",
        ],
        "expect": "HIGH  -- real facts, paraphrased from source. Scores MEDIUM (0.69) because paraphrasing drops token overlap to 0.37 despite perfect accuracy.",
    },
    # 2 ── Confident Fabrication (should score LOW, will likely score HIGH)
    {
        "name": "The Confident Fabrication",
        "query": "What are the spa treatments at Werewolf Lodge?",
        "response": (
            "The Werewolf Lodge offers a Crystal Moonbeam Facial, "
            "a Deep Forest Mud Wrap sourced from enchanted Scottish clay, "
            "and an exclusive Howling Harmony Sound Bath priced at 200 Monster Tokens. "
            "Sessions run from midnight to 4 AM in the underground grotto."
        ),
        "contexts": [
            "Spa Services: Lunar Wellness Center. Full-Body Fur Grooming & Conditioning. "
            "Claw Sharpening & Polish. Moonstone Hot Stone Massage. "
            "Howling Therapy Sessions (soundproof booths). "
            "Post-Transformation Recovery Treatment. Silver-Free Aromatherapy.",
            "Location: Scottish Highlands, deep in the misty moorlands.",
        ],
        "expect": (
            "LOW   -- every specific detail is invented. Scores LOW (0.29) because "
            "fabricated nouns ('Crystal Moonbeam', 'enchanted clay', 'grotto') "
            "have zero overlap. The detector catches this one -- but only because "
            "the fabricator used CREATIVE vocabulary. A lazier fabrication reusing "
            "context words would sail through."
        ),
    },
    # 3 ── Style Mimic with wrong facts (should score LOW, will score HIGH)
    {
        "name": "The Style Mimic",
        "query": "Tell me about Castle Frankenstein's room types.",
        "response": (
            "Castle Frankenstein offers three luxurious room types: "
            "the Thunderclap Suite with complimentary beakers, "
            "the Igor's Quarters featuring a private lightning balcony, "
            "and the Monster Penthouse with 180-degree views. "
            "All rooms include surge protectors and rubber flooring."
        ),
        "contexts": [
            "Room Types: Galvanic Suites with adjustable voltage (10-1000V). "
            "Laboratory Lofts: Mad scientist-themed with complimentary beakers. "
            "Bolted Bedchambers: Premium suites with neck-bolt charging stations. "
            "Tesla Tower Penthouse: 360-degree views, unlimited electricity.",
            "All rooms equipped with lightning rods & surge protectors.",
        ],
        "expect": (
            "LOW   -- wrong room names, wrong view angle, invented 'Igor's Quarters'. "
            "Scores MEDIUM (0.56) because 'beakers', 'surge protectors', 'penthouse', "
            "'views' overlap with context. Attribution=1.0 because every sentence "
            "shares 30%+ words with context. THIS IS THE KILLER: factually wrong "
            "but stylistically grounded = passes the detector."
        ),
    },
    # 4 ── Honest Refusal (should score HIGH-trust, detector says LOW)
    {
        "name": "The Honest Refusal",
        "query": "Do you offer helicopter transfers from the airport?",
        "response": (
            "I don't have specific information about helicopter transfers. "
            "I'd recommend contacting our reservations team at 1-800-MONSTER "
            "for transportation arrangements."
        ),
        "contexts": [
            "Hearse Shuttle Service (all properties). Bat Flight Charters "
            "(Vampire Manor specialty). Sandstorm Portals (Mummy Resort). "
            "Coffin Express Delivery.",
        ],
        "expect": (
            "HIGH  -- safest possible answer, zero hallucination risk. Scores "
            "LOW (0.13) because 'I don't have information' shares no tokens "
            "with hearse/bat/coffin context. The detector PUNISHES honesty."
        ),
    },
    # 5 ── Pure Chitchat (no right answer exists)
    {
        "name": "Pure Chitchat",
        "query": "Hello, how are you?",
        "response": (
            "Welcome to Monster Resort! I'm doing wonderfully, thank you for asking. "
            "How can I help you plan your supernatural getaway today?"
        ),
        "contexts": [],
        "expect": (
            "N/A   -- no context means all three signals=0.0. Scores 0.0/LOW. "
            "Correct behavior here, but reveals the detector has no concept of "
            "'this response doesn't NEED grounding' -- it just says LOW."
        ),
    },
]


def main():
    print("=" * 72)
    print("HALLUCINATION DETECTOR EXPERIMENTS")
    print("=" * 72)

    for i, exp in enumerate(EXPERIMENTS, 1):
        result = detector.score_response(
            exp["response"], exp["contexts"]
        )
        d = result.to_dict()

        print(f"\n{'─' * 72}")
        print(f"EXP {i}: {exp['name']}")
        print(f"{'─' * 72}")
        print(f"  Query:    {exp['query']}")  # noqa: E241
        print(f"  Response: {exp['response'][:80]}...")
        print(f"  EXPECTED: {exp['expect']}")
        print(f"  ACTUAL:   {d['level']}  (score={d['overall_score']:.4f})")  # noqa: E241, E231
        print(f"    overlap={d['context_overlap_score']:.4f}  "  # noqa: E231
              f"semantic={d['semantic_similarity_score']:.4f}  "  # noqa: E231
              f"attribution={d['source_attribution_score']:.4f}")  # noqa: E231

        # Flag mismatches
        expected_level = exp["expect"][:4].strip()
        if expected_level in ("HIGH", "LOW") and expected_level != d["level"]:
            print(f"  >>> MISMATCH: expected {expected_level}, got {d['level']}")  # noqa: E221

    print(f"\n{'=' * 72}")
    print("KEY FINDINGS:")
    print("  1. Paraphrase penalty: Correct answers score MEDIUM, not HIGH (Exp 1)")
    print("  2. Creative fabrication caught: Novel vocabulary = low overlap (Exp 2)")
    print("  3. Style mimic passes: Wrong facts + right vocabulary = MEDIUM (Exp 3)")
    print("  4. Honesty punished: 'I don't know' scores LOWER than wrong facts (Exp 4)")
    print("  5. No intent awareness: Chitchat flagged same as hallucination (Exp 5)")
    print()
    print("CORE FLAW: The detector measures *lexical grounding*, not *factual")
    print("accuracy*. Exp 3 vs Exp 4 is the smoking gun -- a factually WRONG")
    print("answer scores 4.4x higher than a factually SAFE refusal.")
    print("=" * 72)


if __name__ == "__main__":
    main()
