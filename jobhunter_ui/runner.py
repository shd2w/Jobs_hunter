"""Runs the ORIGINAL pipeline scripts (run_scan.py, run_evaluate.py, ...) one at a time and streams output."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from .service import ActionError, GERMAN_POLICIES

TASKS = {
    "scan": ("Find new jobs", "run_scan.py"),
    "evaluate": ("Score and rank new jobs", "run_evaluate.py"),
    "all": ("Do everything (find, score, notify)", "run_all.py"),
    "export": ("Export application queue", "run_export_queue.py"),
    "health": ("Check that everything works", "run_health.py"),
}
MAX_LINES = 3000


class Runner:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self._lock = threading.Lock()
        self._proc: subprocess.Popen | None = None
        self._lines: list[str] = []
        self._dropped = 0
        self.task = None
        self.label = ""
        self.started = None
        self.finished = None
        self.returncode: int | None = None

    def build_args(self, task: str, opts: dict) -> list[str]:
        if task not in TASKS:
            raise ActionError("bad_task", "Unknown task.")
        args = [sys.executable, "-u", str(self.root / TASKS[task][1])]
        thr, pol = opts.get("threshold"), opts.get("german_policy")
        if thr not in (None, ""):
            try:
                t = float(thr)
            except (TypeError, ValueError):
                raise ActionError("bad_value", "Threshold must be a number.")
            if not 1 <= t <= 5:
                raise ActionError("bad_value", "Threshold must be between 1 and 5.")
            if task in ("evaluate", "all"):
                args += ["--threshold", str(t)]
        if pol not in (None, ""):
            if pol not in GERMAN_POLICIES:
                raise ActionError("bad_value", "Unknown German filter option.")
            if task in ("evaluate", "all"):
                args += ["--german-policy", pol]
        if task == "evaluate":
            try:
                raw = opts.get("batch")
                n = 5 if raw in (None, "") else int(raw)
            except (TypeError, ValueError):
                raise ActionError("bad_value", "Batch size must be a whole number.")
            if not 1 <= n <= 100:
                raise ActionError("bad_value", "Batch size must be between 1 and 100.")
            args += ["--batch", str(n)]
            args.append("--create-cv" if opts.get("create_cv") else "--no-cv")
        if task == "all" and opts.get("scan_only"):
            args.append("--scan-only")
        return args

    def start(self, task: str, opts: dict | None = None) -> dict:
        args = self.build_args(task, opts or {})
        with self._lock:
            if self._proc and self._proc.poll() is None:
                raise ActionError("busy", "Another task is still running. Wait for it or stop it.", 409)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
            self._lines, self._dropped = [], 0
            self.task, self.label = task, TASKS[task][0]
            self.started, self.finished, self.returncode = time.time(), None, None
            self._proc = subprocess.Popen(args, cwd=str(self.root), env=env, stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
            threading.Thread(target=self._pump, args=(self._proc,), daemon=True).start()
        return self.status()

    def _pump(self, proc):
        for line in proc.stdout:
            with self._lock:
                self._lines.append(line.rstrip("\n"))
                if len(self._lines) > MAX_LINES:
                    del self._lines[:500]
                    self._dropped += 500
        rc = proc.wait()
        with self._lock:
            self.returncode, self.finished = rc, time.time()

    def stop(self) -> dict:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
        return self.status()

    def status(self, since: int = 0) -> dict:
        with self._lock:
            running = bool(self._proc and self._proc.poll() is None)
            total = self._dropped + len(self._lines)
            start = max(0, since - self._dropped)
            return {"task": self.task, "label": self.label, "running": running, "returncode": self.returncode,
                    "started": self.started, "finished": self.finished,
                    "lines": self._lines[start:], "next": total}
