"""Application layer — use case services.

Orchestrates domain rules and adapters. One service per use case.
"""

from jobhunter.app.result import Err, Ok, Result, err, ok, is_err, is_ok

__all__ = ["Err", "Ok", "Result", "err", "ok", "is_err", "is_ok"]
