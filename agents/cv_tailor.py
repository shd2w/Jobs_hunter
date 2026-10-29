"""Retired compatibility entry point. CVs must remain candidate-supplied and unchanged."""

class CVTailor:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("CV generation and tailoring are retired. Use ATS keyword recommendations only.")

    def tailor(self, *args, **kwargs):
        raise RuntimeError("CV generation and tailoring are prohibited.")
