"""Disposable full HTTP lifecycle. QA needs pytest; runtime application does not."""
import json,sys,tempfile
from pathlib import Path
import pytest
root=Path(sys.argv[1]).resolve();sys.path.insert(0,str(root))
from tests.test_phase5_acceptance import isolated,lifecycle
with tempfile.TemporaryDirectory(prefix='jobhunter-integrated-') as td,pytest.MonkeyPatch.context() as patch:
 fixture=isolated.__wrapped__(Path(td),patch)
 result=lifecycle(*fixture)
result.update(schema=5,data='disposable synthetic records only',runtime='real loopback HTTP with fixture collection and fake delivery, not live providers')
print(json.dumps(result,indent=2))
