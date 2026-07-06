"""Small, dependency-free validation helpers reused across modules."""

from __future__ import annotations

from typing import Optional


def ensure_odd_positive(value: int, name: str = "value") -> int:
    if not isinstance(value, int) or value < 1 or value % 2 == 0:
        raise ValueError(f"{name} must be a positive odd integer, got {value!r}")
    return value


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def nearest_index(sorted_values, target: float, tolerance: Optional[float] = None) -> Optional[int]:
    """Index of the value in a sorted 1D sequence nearest to ``target``,
    or ``None`` if ``tolerance`` is given and exceeded by the closest
    match. Uses a simple linear scan (band counts are small — tens to a
    couple hundred — so this is not a performance concern here).
    """
    if len(sorted_values) == 0:
        return None
    best_idx = 0
    best_diff = abs(sorted_values[0] - target)
    for i in range(1, len(sorted_values)):
        diff = abs(sorted_values[i] - target)
        if diff < best_diff:
            best_diff = diff
            best_idx = i
    if tolerance is not None and best_diff > tolerance:
        return None
    return best_idx
