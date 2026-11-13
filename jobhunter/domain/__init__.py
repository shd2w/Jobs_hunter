"""Domain layer — pure rules, no I/O.

Scoring, eligibility, dedup, profile-truth, salary and seniority rules.
No network, no file system, no external packages beyond stdlib.
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
    compute_domain_score,
)
from jobhunter.domain.filters import (  # noqa: F401
    TitleFilter,
    LocationFilter,
    filter_jobs,
)

__all__ = [
    "DIMENSIONS",
    "DEFAULT_WEIGHTS",
    "job_id",
    "parse_weights",
    "is_default",
    "score_of",
    "tier",
    "rank",
    "compute_domain_score",
    "TitleFilter",
    "LocationFilter",
    "filter_jobs",
]
