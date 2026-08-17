# Report generator, packaged for a Hugging Face Space.
# Same Python the app runs locally — nothing here changes the report.
FROM python:3.12-slim

WORKDIR /app

# Matplotlib and Pillow want a writable cache; Spaces run as a non-root user.
ENV MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/tmp \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY generate.py radon_report.py ./

EXPOSE 7860
CMD ["uvicorn", "generate:app", "--host", "0.0.0.0", "--port", "7860"]
