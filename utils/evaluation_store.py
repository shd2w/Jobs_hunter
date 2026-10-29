"""Legacy JSON compatibility store: locked, atomic, fail-closed persistence.

Malformed originals are never reset or overwritten. Repair them explicitly after
backing them up. The new local workflow uses SQLite instead; this module remains
for existing CLI/UAA integrations.
"""
from __future__ import annotations
import json
import math
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from filelock import FileLock


def _default_output_path() -> Path:
    return Path('data/evaluations.json')


def _safe_serialize(obj: Any) -> Any:
    if isinstance(obj, float) and not math.isfinite(obj):
        raise ValueError('Non-finite evaluation number')
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(x) for x in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def load_evaluations(output_path: Path | str | None = None) -> list[dict[str, Any]]:
    path = Path(output_path) if output_path else _default_output_path()
    if not path.exists():
        return []
    with path.open(encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list) or any(not isinstance(r, dict) for r in data):
        raise ValueError(f'{path}: expected an array of evaluation objects; original preserved')
    return data


def append_evaluation(evaluation: dict[str, Any], output_path: Path | str | None = None) -> Path:
    if not isinstance(evaluation, dict):
        raise ValueError('Evaluation must be an object')
    path = Path(output_path) if output_path else _default_output_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(str(path) + '.lock', timeout=30):
        records = load_evaluations(path)
        record = _safe_serialize(evaluation)
        record['appended_at'] = datetime.now(timezone.utc).isoformat()
        url = record.get('url')
        if url:
            records = [r for r in records if r.get('url') != url]
        records.append(record)
        fd, temp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(records, f, ensure_ascii=False, indent=2, allow_nan=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp, path)
        finally:
            Path(temp).unlink(missing_ok=True)
    return path
