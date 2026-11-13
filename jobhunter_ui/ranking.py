"""Deterministic job ranking over stored evaluations (pure functions, no I/O).

Re-exports from jobhunter.domain.scoring for backward compatibility.
"""

from jobhunter.domain.scoring import (  # noqa: F401
    DIMENSIONS,
    DEFAULT_WEIGHTS,
    job_id,
    parse_weights,
    is_default,
    score_of,
    tier,
    rank,
)
