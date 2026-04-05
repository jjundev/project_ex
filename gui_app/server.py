from __future__ import annotations

import os
import socketserver
import subprocess
import time
from http.server import HTTPServer

class _ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address) -> None:  # type: ignore[override]
        """클라이언트 연결 중단 등 무해한 소켓 오류는 조용히 무시한다."""
        import sys
        exc = sys.exc_info()[1]
        _IGNORED_CONN_ERRORS = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)
        if isinstance(exc, _IGNORED_CONN_ERRORS):
            return
        super().handle_error(request, client_address)

def _free_port(port: int) -> None:
    """해당 포트를 점유 중인 프로세스를 종료한다."""
    import signal
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            try:
                os.kill(int(pid), signal.SIGTERM)
            except (ProcessLookupError, ValueError):
                pass
        if pids:
            time.sleep(0.3)
    except FileNotFoundError:
        pass  # lsof 없는 환경(Windows)은 건너뜀
