FROM python:3.12-slim
WORKDIR /app
COPY requirements-scanners.lock .
RUN pip install --no-cache-dir -r requirements-scanners.lock \
    && useradd --create-home app \
    && mkdir -p /app/data /app/output \
    && chown -R app:app /app
COPY --chown=app:app . .
USER app
# Original collection entry point restored; no listening network service.
CMD ["python", "run_scan.py"]
