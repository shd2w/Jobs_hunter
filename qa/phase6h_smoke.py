"""Integrated synthetic acceptance. Usage: python qa/phase6h_smoke.py REPO_ROOT."""
import json
from pathlib import Path
import sys
import tempfile
import pytest
root = Path(sys.argv[1]).resolve(); sys.path.insert(0, str(root))
from tests.test_phase6_acceptance import workspace, lifecycle
with tempfile.TemporaryDirectory(prefix='jobhunter-phase6h-') as td, pytest.MonkeyPatch.context() as patch:
    result = lifecycle(workspace.__wrapped__(Path(td), patch))
print(json.dumps(result, indent=2))
