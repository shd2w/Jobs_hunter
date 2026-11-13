"""JobHunter layered package.

Layers:
- domain: pure rules (scoring, eligibility, dedup); no I/O
- app: application services (use cases over domain + adapters)
- adapters: external I/O (scanners, AI, PDF, network, etc.)
- interfaces: CLI and UI; parse input, call one service method, render Result[T]
"""
__version__ = "0.2.0"
