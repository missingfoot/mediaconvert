"""Shared pause/stop control for a running conversion batch.

One instance is created per batch (or per individually-converted selection)
and passed down from the UI's worker thread into the conversion backend, so
Stop can terminate whatever subprocess is currently running from the main
thread without the backend needing to know anything about Qt.
"""

import subprocess
import threading


class ConversionControl:
    def __init__(self) -> None:
        self.stop_requested = threading.Event()
        self.pause_requested = threading.Event()
        self._lock = threading.Lock()
        self._current_process: subprocess.Popen | None = None

    def set_current_process(self, proc: subprocess.Popen | None) -> None:
        with self._lock:
            self._current_process = proc

    def request_stop(self) -> None:
        """Signal the worker loop to stop after the current job, and kill
        whatever subprocess is running right now so the current job doesn't
        wait for a full encode to finish."""
        self.stop_requested.set()
        with self._lock:
            if self._current_process is not None:
                self._current_process.terminate()

    def wait_while_paused(self) -> None:
        """Block here while paused, waking early if a stop comes in."""
        while self.pause_requested.is_set() and not self.stop_requested.is_set():
            self.stop_requested.wait(timeout=0.2)
