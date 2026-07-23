#!/usr/bin/env python3
"""
Framework Backtest: old unconditional 3× vs 15% distance vs delta-based V2.

For each position, evaluates what each framework would have said at key decision
points: entry, cut (if applicable), and current mark.

Outputs a decision matrix for comparison.
"""
import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pricing import calc_put_delta, bs_put_greeks

# ── Framework constants ──────────────────────────────────────────
# All three frameworks share the 3× escalation threshold
CUT_LOSS_MULTIPLE = 3.0

# Framework A: old unconditional
#   "mid >= 3× credit → exit. No exemptions."

# Framework B: 15% distance (yesterday's intermediate, deprecated)
CUT_DISTANCE_THRESHOLD = 0.15

# Framework C: delta-based V2 (current)
CUT_LOSS_MULTIPLE = 3.0
CONFIRMED_LOSS_MULTIPLE = 1.5  # Loss must be ≥ 1.5× for delta exit to fire
DELTA_HARD_EXIT = 0.35
DELTA_SOFT_WATCH = 0.25
DELTA_LOW_EXPOSURE = 0.15

def framework_a_old_unconditional(credit, opt_mid):
    """Return (signal, label) for old unconditional rule."""
    if credit and opt_mid and opt_mid >= credit * CUT_LOSS_MULTIPLE:
        return "RED", "EXIT (unconditional 3×)"
    return "GREEN", "OK"


def framework_b_distance(credit, opt_mid, spot, strike):
    """Return (signal, label) for 15% distance rule."""
    if not (credit and opt_mid and opt_mid >= credit * CUT_LOSS_MULTIPLE):
        return "GREEN", "OK"
    if strike and spot:
        distance = (spot - strike) / strike
        if distance <= CUT_DISTANCE_THRESHOLD:
            return "RED", "EXIT (3×, within 15%)"
        else:
            return "YELLOW", f"WATCH (3×, {distance*100:.0f}% above strike)"
    return "RED", "EXIT (3×, no distance data)"


def framework_c_delta(credit, opt_mid, spot, strike, dte, iv):
    """Return (signal, label) for delta-based V2 rule with loss gating."""
    if not (credit and opt_mid and opt_mid >= credit * CUT_LOSS_MULTIPLE):
        return "GREEN", "OK"

    abs_delta = _resolve_delta(None, spot, strike, dte, iv)

    if abs_delta is None:
        return "YELLOW", "ESCALATE (3×, no delta)"

    loss_confirmed = opt_mid >= credit * CONFIRMED_LOSS_MULTIPLE

    if abs_delta >= DELTA_HARD_EXIT and loss_confirmed:
        return "RED", f"EXIT (3×, delta {abs_delta:.2f}, confirmed)"
    elif abs_delta >= DELTA_HARD_EXIT:
        return "YELLOW", f"WATCH (3×, delta {abs_delta:.2f}, unconfirmed)"
    elif abs_delta >= DELTA_SOFT_WATCH and loss_confirmed:
        return "YELLOW", f"WATCH (3×, delta {abs_delta:.2f})"
    elif abs_delta < DELTA_LOW_EXPOSURE:
        return "YELLOW", f"WATCH (3×, delta {abs_delta:.2f} low exposure)"
    else:
        return "YELLOW", f"WATCH (3×, delta {abs_delta:.2f})"


def _resolve_delta(chain_delta, spot, strike, dte, iv):
    """Resolve put delta from chain or estimate via BS."""
    if chain_delta is not None:
        return abs(chain_delta)
    if all([spot, strike, dte, iv]) and dte > 0 and iv > 0:
        try:
            T = max(dte / 365.0, 1 / 365.0)
            return abs(calc_put_delta(spot, strike, iv, T))
        except (ValueError, ZeroDivisionError):
            return None
    return None


def evaluate_position(name, credit, spot, strike, dte, iv,
                      opt_mid=None, chain_delta=None, actual_pnl=None,
                      actual_action=None):
    """Evaluate a position snapshot against all three frameworks.

    Returns dict with each framework's verdict.
    """
    result = {
        "name": name,
        "spot": spot,
        "strike": strike,
        "dte": dte,
        "iv_pct": round(iv * 100, 1) if iv else None,
        "credit": credit,
        "opt_mid": opt_mid,
        "loss_multiple": round(opt_mid / credit, 2) if (credit and opt_mid) else None,
        "actual_pnl": actual_pnl,
        "actual_action": actual_action,
    }

    # Compute distance and delta for context
    if strike and spot:
        result["distance_pct"] = round((spot - strike) / strike * 100, 1)
    abs_delta = _resolve_delta(chain_delta, spot, strike, dte, iv)
    if abs_delta is not None:
        result["delta"] = round(abs_delta, 4)

    # Evaluate all three frameworks
    result["A_old_unconditional"] = framework_a_old_unconditional(credit, opt_mid)
    result["B_15pct_distance"] = framework_b_distance(credit, opt_mid, spot, strike)
    result["C_delta_v2"] = framework_c_delta(credit, opt_mid, spot, strike, dte, iv)

    return result


def format_matrix(results):
    """Format results as a comparison matrix."""
    lines = []
    lines.append("## Framework Backtest: Decision Matrix")
    lines.append("")
    lines.append("| Position | Spot | Strike | DTE | IV | 3× Mult | Δ | A (Old) | B (15%) | C (Delta) | Actual |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")

    for r in results:
        name = r["name"]
        spot = f"${r['spot']:.2f}" if r["spot"] else "N/A"
        strike = f"${r['strike']:.0f}" if r["strike"] else "N/A"
        dte = str(r["dte"]) if r["dte"] else "N/A"
        iv = f"{r['iv_pct']:.0f}%" if r["iv_pct"] else "N/A"
        mult = f"{r['loss_multiple']:.2f}×" if r["loss_multiple"] else "N/A"
        delta = f"{r['delta']:.3f}" if r.get("delta") else "N/A"

        a_sig, a_label = r["A_old_unconditional"]
        b_sig, b_label = r["B_15pct_distance"]
        c_sig, c_label = r["C_delta_v2"]

        a_cell = f"**{a_sig}** {a_label}" if a_sig != "GREEN" else a_sig
        b_cell = f"**{b_sig}** {b_label}" if b_sig != "GREEN" else b_sig
        c_cell = f"**{c_sig}** {c_label}" if c_sig != "GREEN" else c_sig

        actual = r.get("actual_action") or r.get("actual_pnl") or "—"

        lines.append(f"| {name} | {spot} | {strike} | {dte} | {iv} | {mult} | {delta} | {a_cell} | {b_cell} | {c_cell} | {actual} |")

    lines.append("")
    lines.append("**Key:** RED = exit recommendation. YELLOW = watch/escalate. GREEN = no action. ORANGE = MA50 broken (not shown here).")
    lines.append("")
    return "\n".join(lines)


def format_detail(results):
    """Format per-position detail for each framework divergence."""
    lines = []
    lines.append("## Framework Divergences")
    lines.append("")
    lines.append("Only positions where frameworks disagree are shown.")
    lines.append("")

    for r in results:
        a_sig, _ = r["A_old_unconditional"]
        b_sig, _ = r["B_15pct_distance"]
        c_sig, _ = r["C_delta_v2"]

        # Check if any frameworks disagree
        signals = {a_sig, b_sig, c_sig}
        if len(signals) <= 1:
            continue

        lines.append(f"### {r['name']}")
        lines.append("")
        lines.append(f"Spot: ${r['spot']:.2f} | Strike: ${r['strike']:.0f} | DTE: {r['dte']} | IV: {r['iv_pct']:.0f}%")
        if r.get("distance_pct"):
            lines.append(f"Distance above strike: {r['distance_pct']}%")
        if r.get("delta"):
            lines.append(f"Put delta: {r['delta']:.4f}")
        lines.append(f"Option mid: ${r['opt_mid']:.2f} | Multiplier: {r['loss_multiple']:.2f}×")
        lines.append("")

        lines.append(f"| Framework | Signal | Reasoning |")
        lines.append(f"|---|---|---|")
        lines.append(f"| A (Old unconditional) | **{a_sig}** | {r['A_old_unconditional'][1]} |")
        lines.append(f"| B (15% distance) | **{b_sig}** | {r['B_15pct_distance'][1]} |")
        lines.append(f"| C (Delta V2) | **{c_sig}** | {r['C_delta_v2'][1]} |")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    # This script is designed to be imported and called with position data.
    # For standalone use, pass JSON on stdin or define positions inline.
    print("Backtest module loaded. Import and call evaluate_position() or run full suite.")
