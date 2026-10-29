FROM python:3.12-slim
WORKDIR /app
COPY requirements-local.txt .
RUN pip install --no-cache-dir -r requirements-local.txt \
    && useradd --create-home app \
    && mkdir -p /app/data /app/output \
    && chown -R app:app /app
COPY --chown=app:app . .
USER app
# Manual CLI container; no implicit browser installation or background schedule.
CMD ["python", "run_local.py", "init"]
