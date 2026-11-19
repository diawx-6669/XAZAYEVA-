"""Metrics and rewards (exact arithmetic with Fraction, converted to float at the end).

shared reward     = clip(2*F1 - 1 - 0.002*inspection_steps, -1, 1)   (the case's common reward)
experimental      = same formula, but a TP counts only if every ID of the satisfied evidence
                    set was actually returned to the agent in an observation; otherwise that
                    finding is an FP and the issue an FN. Reported separately, never mixed.
"""

from fractions import Fraction

STEP_COST = Fraction(2, 1000)


def prf(tp: int, fp: int, fn: int):
    p = Fraction(tp, tp + fp) if tp + fp else Fraction(0)
    r = Fraction(tp, tp + fn) if tp + fn else Fraction(0)
    n_truth, n_find = tp + fn, tp + fp
    if n_truth == 0 and n_find == 0:
        f1 = Fraction(1)
    elif n_truth == 0:
        f1 = Fraction(0)
    else:
        f1 = Fraction(2 * tp, 2 * tp + fp + fn)
    return p, r, f1


def shared_reward(f1, inspection_steps: int) -> float:
    v = 2 * Fraction(f1) - 1 - STEP_COST * inspection_steps
    return float(max(Fraction(-1), min(Fraction(1), v)))
