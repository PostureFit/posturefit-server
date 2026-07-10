FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir gunicorn && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local /usr/local

COPY . .

# Pre-download MediaPipe pose model (heavy) while still root
RUN python3 -c "import mediapipe.python.solutions.pose as p; p.Pose(static_image_mode=True, model_complexity=2).close()"

RUN adduser --disabled-password --no-create-home appuser && \
    mkdir -p static/profiles static/scans && \
    chown -R appuser:appuser /app

# MediaPipe always tries to re-download model on init → make its dir writable for appuser
RUN chown -R appuser:appuser /usr/local/lib/python3.12/site-packages/mediapipe/modules

USER appuser

EXPOSE 8000

CMD ["gunicorn", "main:app", \
     "--bind", "0.0.0.0:8000", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "1", \
     "--threads", "2", \
     "--max-requests", "500", \
     "--max-requests-jitter", "50", \
     "--timeout", "60", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--limit-request-line", "4094", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
