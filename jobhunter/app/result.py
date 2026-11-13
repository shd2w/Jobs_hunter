"""Result[T] — discriminated union for service layer outcomes.

Ok(value) represents success; Err(error) represents failure.
Services return Result[T] so callers handle failures explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err(Generic[T]):
    error: str
    code: str = "unknown"


Result = Ok[T] | Err[T]


def ok(value: T) -> Ok[T]:
    return Ok(value=value)


def err(error: str, code: str = "unknown") -> Err[T]:
    return Err(error=error, code=code)


def is_ok(result: Result[T]) -> bool:
    return isinstance(result, Ok)


def is_err(result: Result[T]) -> bool:
    return isinstance(result, Err)
