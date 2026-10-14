"""Linux production process ownership, using real child/grandchild processes."""
import ctypes
from dataclasses import replace
import os
import sys
import time

import pytest

from officecli_openapi_proof.officecli import OfficeCliFailure, SubprocessOfficeCliExecutor
from test_guidance_routes import settings

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux production process groups')


@pytest.mark.parametrize('outcome', ['success', 'error', 'timeout'])
def test_nonresident_call_leaves_no_live_descendant(tmp_path, outcome):
    # Act as the container init for this test, so adopted grandchildren can be
    # reaped and their actual termination observed, rather than inferred from mocks.
    libc = ctypes.CDLL(None, use_errno=True)
    previous = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(previous), 0, 0, 0) == 0  # GET_CHILD_SUBREAPER
    assert libc.prctl(36, 1, 0, 0, 0) == 0  # SET_CHILD_SUBREAPER
    pid_file = tmp_path / 'descendant.pid'
    code = (
        "import subprocess,sys,time,pathlib;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid));"
        "print('native result',flush=True);"
        + ("time.sleep(60)" if outcome == 'timeout' else f"sys.exit({7 if outcome == 'error' else 0})")
    )
    executor = SubprocessOfficeCliExecutor(replace(settings(), binary=sys.executable, timeout_seconds=1))
    descendant = None
    try:
        if outcome == 'success':
            assert executor.run('-c', code, str(pid_file)).text.strip() == 'native result'
        else:
            with pytest.raises(OfficeCliFailure, match='timed out' if outcome == 'timeout' else 'native result'):
                executor.run('-c', code, str(pid_file))
        descendant = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            pid, status = os.waitpid(descendant, os.WNOHANG)
            if pid:
                descendant = None
                assert os.WIFSIGNALED(status)
                return
            time.sleep(0.02)
        pytest.fail('CLI invocation left its descendant running')
    finally:
        if descendant:
            os.kill(descendant, 9)
            os.waitpid(descendant, 0)
        assert libc.prctl(36, previous.value, 0, 0, 0) == 0
