# Report generator, packaged for Render. Built from the repository root.
# Same Python the app runs locally — nothing here changes the report.
FROM python:3.12-slim

WORKDIR /app

ENV MPLCONFIGDIR=/tmp/matplotlib \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/generate.py api/radon_report.py ./

# Render supplies PORT. Shell form so it expands at run time.
CMD uvicorn generate:app --host 0.0.0.0 --port ${PORT:-10000}
