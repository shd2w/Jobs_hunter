"""Title and location filters for job postings.

Re-exports from jobhunter.domain.filters for backward compatibility.
"""

from jobhunter.domain.filters import (  # noqa: F401
    TitleFilter,
    LocationFilter,
    filter_jobs,
)
