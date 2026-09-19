#!/usr/bin/env python3
"""Exact Generation VI/VII capture odds.

The implementation follows the Gen VI/VII integer capture path described by
Bulbapedia's ``Catch rate`` article and the Dragonfly Cave mechanics reference:
https://bulbapedia.bulbagarden.net/wiki/Catch_rate
https://www.dragonflycave.com/mechanics/gen-vi-vii-capturing/

This tool deliberately has no species database.  Supply the species' Gen VI/VII
catch rate with ``--rate``; a missing rate is an error rather than an invented
lookup.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import Decimal, ROUND_FLOOR, getcontext
from fractions import Fraction
from typing import Any

getcontext().prec = 80
MAX_A = 255 * 4096
MAX_B = 65536

STATUS_MULTIPLIERS = {
    "none": Fraction(1),
    "normal": Fraction(1),
    "par": Fraction(3, 2),
    "paralysis": Fraction(3, 2),
    "paralyzed": Fraction(3, 2),
    "brn": Fraction(3, 2),
    "burn": Fraction(3, 2),
    "psn": Fraction(3, 2),
    "poison": Fraction(3, 2),
    "tox": Fraction(3, 2),
    "badly-poisoned": Fraction(3, 2),
    "sleep": Fraction(5, 2),
    "slp": Fraction(5, 2),
    "freeze": Fraction(5, 2),
    "frz": Fraction(5, 2),
}

# Context-free values are exact for the named ball.  Conditional balls are
# resolved only when the caller supplies a matching context.
BALL_MULTIPLIERS = {
    "poke": Fraction(1),
    "pokeball": Fraction(1),
    "premier": Fraction(1),
    "premierball": Fraction(1),
    "luxury": Fraction(1),
    "luxuryball": Fraction(1),
    "heal": Fraction(1),
    "healball": Fraction(1),
    "great": Fraction(3, 2),
    "greatball": Fraction(3, 2),
    "ultra": Fraction(2),
    "ultraball": Fraction(2),
    "safari": Fraction(3, 2),
    "quick": Fraction(5),
    "quickball": Fraction(5),
    "fast": Fraction(4),
    "fastball": Fraction(4),
    "love": Fraction(8),
    "loveball": Fraction(8),
    "lure": Fraction(5),
    "lureball": Fraction(5),
    "moon": Fraction(4),
    "moonball": Fraction(4),
    "beast": Fraction(5),
    "beastball": Fraction(5),
}


def _fraction(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, int):
        return Fraction(value)
    return Fraction(str(value))


def _floor_fraction(value: Fraction) -> int:
    return value.numerator // value.denominator


def normalize_status(status: str) -> str:
    key = re.sub(r"[^a-z-]", "", str(status).lower())
    if key not in STATUS_MULTIPLIERS:
        choices = ", ".join(sorted(STATUS_MULTIPLIERS))
        raise ValueError(f"unknown status {status!r}; use one of: {choices}")
    if key in {"normal", "none"}:
        return "none"
    if key in {"par", "paralyzed"}:
        return "paralysis"
    if key in {"brn", "burn"}:
        return "burn"
    if key in {"psn", "poison", "tox", "badly-poisoned"}:
        return "poison"
    if key in {"slp"}:
        return "sleep"
    if key in {"frz"}:
        return "freeze"
    return key


def _context_tokens(context: str | None) -> set[str]:
    return {re.sub(r"[^a-z0-9]", "", item.lower()) for item in (context or "").split(",") if item.strip()}


def ball_multiplier(
    ball: str | int | float,
    *,
    generation: int = 7,
    context: str | None = None,
    turns: int = 0,
) -> Fraction:
    """Resolve a numeric or named Gen VI/VII ball multiplier.

    Conditional balls intentionally fall back to 1x without a context instead
    of assuming that the condition applies.
    """
    if generation not in (6, 7):
        raise ValueError("generation must be 6 or 7")
    if isinstance(ball, (int, float)) or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", str(ball).strip()):
        value = _fraction(ball)
        if value <= 0:
            raise ValueError("ball multiplier must be positive")
        return value
    key = re.sub(r"[^a-z0-9]", "", str(ball).lower())
    tokens = _context_tokens(context)
    if key in {"net", "netball"}:
        active = {"water", "bug"} & tokens
        return (Fraction(7, 2) if generation == 7 else Fraction(3)) if active else Fraction(1)
    if key in {"dive", "diveball"}:
        return Fraction(7, 2) if {"water", "surfing", "fishing"} & tokens else Fraction(1)
    if key in {"repeat", "repeatball"}:
        return (Fraction(7, 2) if generation == 7 else Fraction(3)) if "caught" in tokens else Fraction(1)
    if key in {"dusk", "duskball"}:
        return Fraction(3) if generation == 7 and {"night", "cave"} & tokens else (
            Fraction(7, 2) if generation == 6 and {"night", "cave"} & tokens else Fraction(1)
        )
    if key in {"timer", "timerball"}:
        if turns < 0:
            raise ValueError("turns must be non-negative")
        return min(Fraction(4), Fraction(1) + Fraction(turns * 1229, 4096))
    if key in {"quick", "quickball"}:
        return Fraction(5) if turns == 0 else Fraction(1)
    if key in {"fast", "fastball"}:
        return Fraction(4) if "speed100" in tokens else Fraction(1)
    if key in {"love", "loveball"}:
        return Fraction(8) if "oppositegender" in tokens else Fraction(1)
    if key in {"lure", "lureball"}:
        return Fraction(5) if {"fishing", "water"} & tokens else Fraction(1)
    if key in {"moon", "moonball"}:
        return Fraction(4) if "moonstone" in tokens else Fraction(1)
    if key in {"beast", "beastball"}:
        return Fraction(5) if "ultrabeast" in tokens else Fraction(410, 4096)
    if key in {"nest", "nestball"}:
        level = next((int(t[5:]) for t in tokens if t.startswith("level") and t[5:].isdigit()), 30)
        return Fraction(41 - level, 10) if level < 30 else Fraction(1)
    if key in {"master", "masterball"}:
        raise ValueError("Master Ball bypasses the capture formula; no odds calculation is needed")
    try:
        return BALL_MULTIPLIERS[key]
    except KeyError as exc:
        raise ValueError(f"unknown ball {ball!r}; use a numeric multiplier or a supported Gen VI/VII ball") from exc


def dex_modifier(caught_count: int) -> Fraction:
    if caught_count < 0:
        raise ValueError("caught-count must be non-negative")
    if caught_count <= 30:
        return Fraction(0)
    if caught_count <= 150:
        return Fraction(1, 2)
    if caught_count <= 300:
        return Fraction(1)
    if caught_count <= 450:
        return Fraction(3, 2)
    if caught_count <= 600:
        return Fraction(2)
    return Fraction(5, 2)


def _decimal_floor(value: Decimal) -> int:
    return int(value.to_integral_value(rounding=ROUND_FLOOR))


def balls_for_probability(per_ball: float, target: float) -> int | None:
    """Return the minimum independent throws reaching ``target`` cumulatively."""
    if not 0 <= per_ball <= 1 or not 0 < target <= 1:
        raise ValueError("per-ball probability must be in [0, 1] and target in (0, 1]")
    if per_ball == 0:
        return None
    if per_ball == 1:
        return 1
    return max(1, math.ceil(math.log1p(-target) / math.log1p(-per_ball)))


def calculate_catch_odds(
    max_hp: int,
    current_hp: int,
    rate: int | float,
    ball: str | int | float,
    status: str = "none",
    roto: int | float = 2,
    caught_count: int = 0,
    *,
    generation: int = 7,
    context: str | None = None,
    turns: int = 0,
) -> dict[str, Any]:
    """Calculate regular, critical, and mixed Gen VI/VII capture probability."""
    if max_hp <= 0 or not 0 <= current_hp <= max_hp:
        raise ValueError("current HP must be between 0 and max HP, with max HP positive")
    rate_f = _fraction(rate)
    roto_f = _fraction(roto)
    if rate_f <= 0 or roto_f <= 0:
        raise ValueError("rate and Roto multiplier must be positive")
    status_name = normalize_status(status)
    status_f = STATUS_MULTIPLIERS[status_name]
    ball_f = ball_multiplier(ball, generation=generation, context=context, turns=turns)

    hp_term = Fraction(3 * max_hp - 2 * current_hp, 3 * max_hp)
    # The game floors this high-precision base before status and Roto modifiers.
    base_a = _floor_fraction(hp_term * 4096 * rate_f * ball_f)
    a = _floor_fraction(Fraction(base_a) * status_f * roto_f)
    a = min(MAX_A, max(0, a))

    if a >= MAX_A:
        b = MAX_B
    else:
        ratio = Decimal(a) / Decimal(MAX_A)
        b = _decimal_floor(Decimal(MAX_B) * (ratio ** (Decimal(3) / Decimal(16))))
    b_ratio = Decimal(b) / Decimal(MAX_B)
    regular = b_ratio**4

    dex = dex_modifier(int(caught_count))
    critical_threshold = _floor_fraction(Fraction(min(a, MAX_A), 4096) * dex / 6)
    critical_chance = Decimal(critical_threshold) / Decimal(256)
    critical_success = critical_chance * b_ratio  # one shake check for a critical capture
    total = (Decimal(1) - critical_chance) * regular + critical_success
    total_float = float(total)

    return {
        "inputs": {
            "max_hp": int(max_hp),
            "current_hp": int(current_hp),
            "rate": float(rate_f) if rate_f.denominator != 1 else rate_f.numerator,
            "ball": str(ball),
            "ball_multiplier": float(ball_f),
            "status": status_name,
            "status_multiplier": float(status_f),
            "roto": float(roto_f) if roto_f.denominator != 1 else roto_f.numerator,
            "caught_count": int(caught_count),
            "dex_modifier": float(dex),
            "generation": generation,
            "context": context or "",
            "turns": turns,
        },
        "base_a": base_a,
        "a": a,
        "b": b,
        "critical_threshold": critical_threshold,
        "probabilities": {
            "regular": float(regular),
            "critical": float(critical_chance),
            "critical_success": float(critical_success),
            "total": total_float,
        },
        # Flat aliases make the pure-function result convenient for callers while
        # the nested probabilities object remains the JSON contract.
        "regular_probability": float(regular),
        "critical_probability": float(critical_chance),
        "critical_success_probability": float(critical_success),
        "total_probability": total_float,
        "cumulative_balls": {
            "50_percent": balls_for_probability(total_float, 0.50),
            "95_percent": balls_for_probability(total_float, 0.95),
        },
    }


# Friendly aliases for callers that use the shorter name.
calculate = calculate_catch_odds
compute_catch_odds = calculate_catch_odds


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Exact Gen VI/VII capture odds; --rate is required.")
    parser.add_argument("--max-hp", type=int, help="target maximum HP")
    parser.add_argument("--current-hp", type=int, help="target current HP")
    parser.add_argument("--hp", nargs=2, type=int, metavar=("CURRENT", "MAX"), help="alternative explicit HP pair")
    parser.add_argument("--rate", required=True, type=float, help="species catch rate; no species lookup is performed")
    parser.add_argument("--ball", required=True, help="numeric multiplier or a supported ball name")
    parser.add_argument("--status", default="none", help="none, paralysis, burn, poison, sleep, or freeze")
    parser.add_argument("--roto", type=float, default=2, help="Roto Catch multiplier (default: 2)")
    parser.add_argument("--caught-count", type=int, default=0, help="number of species registered as caught")
    parser.add_argument("--generation", type=int, choices=(6, 7), default=7)
    parser.add_argument("--context", default="", help="comma-separated ball context, e.g. water,night,caught")
    parser.add_argument("--turns", type=int, default=0, help="turns passed, for Timer Ball")
    parser.add_argument("--json", action="store_true", help="emit structured JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    current_hp, max_hp = (args.hp if args.hp else (args.current_hp, args.max_hp))
    if current_hp is None or max_hp is None:
        print("error: provide --current-hp and --max-hp, or --hp CURRENT MAX", file=sys.stderr)
        return 2
    try:
        result = calculate_catch_odds(
            max_hp,
            current_hp,
            args.rate,
            args.ball,
            args.status,
            args.roto,
            args.caught_count,
            generation=args.generation,
            context=args.context,
            turns=args.turns,
        )
    except (TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        payload = {
            **result,
            "mechanics": {
                "source": "Gen VI/VII capture mechanics",
                "formula": "a=floor(hp_term*4096*rate*ball), then status and Roto; cap at 255*4096; b=floor(65536*(a/(255*4096))^(3/16)); regular=(b/65536)^4; critical=threshold/256 with one-shake success; total is the mixture",
                "roto_default": 2,
            },
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    p = result["probabilities"]
    i = result["inputs"]
    print("Gen VI/VII capture mechanics")
    print("  a = floor(hp term * 4096 * rate * ball), then status and Roto; capped at 255*4096")
    print("  b = floor(65536 * (a / (255*4096)) ** (3/16)); regular = (b/65536)^4")
    print("  critical threshold = floor(min(a/4096,255) * dex_modifier / 6); critical uses one shake")
    print(f"  inputs: HP {i['current_hp']}/{i['max_hp']}, rate {i['rate']}, ball x{i['ball_multiplier']}, status {i['status']}, Roto x{i['roto']}, caught {i['caught_count']}")
    print(f"  intermediates: base a={result['base_a']}, a={result['a']}, b={result['b']}, critical threshold={result['critical_threshold']}")
    print(f"  regular: {p['regular']:.9%}")
    print(f"  critical chance: {p['critical']:.9%}; critical success: {p['critical_success']:.9%}")
    print(f"  total per ball: {p['total']:.9%}")
    print(f"  balls for cumulative 50%: {result['cumulative_balls']['50_percent']}")
    print(f"  balls for cumulative 95%: {result['cumulative_balls']['95_percent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
