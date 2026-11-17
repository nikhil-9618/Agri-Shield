# AgriShield API — production image for Render (Docker runtime).
#
# Small by design: the LiteRT runtime runs the TFLite model without importing
# TensorFlow, so the service fits a 512 MB instance. Grad-CAM is off here; see
# backend/requirements-gradcam.txt for the explanation-capable variant.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=10000 \
    APP_ENV=production \
    GRADCAM_ENABLED=false \
    DATABASE_URL=sqlite:////tmp/agrishield.db \
    UPLOAD_DIR=/tmp/agrishield-uploads \
    MODEL_PATH=ml/artifacts/agrishield_model.tflite \
    CLASS_NAMES_PATH=ml/artifacts/class_names.json \
    ADVISORY_DIR=advisory

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements-render.txt backend/requirements-render.txt
RUN pip install --no-cache-dir -r backend/requirements-render.txt

# Only what the API needs at runtime: code, advisory JSON, model + labels.
COPY backend backend
COPY advisory advisory
COPY ml/artifacts/agrishield_model.tflite ml/artifacts/agrishield_model.tflite
COPY ml/artifacts/class_names.json ml/artifacts/class_names.json
COPY ml/artifacts/training_report.json ml/artifacts/training_report.json
COPY database database

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /tmp/agrishield-uploads \
    && chown -R app:app /tmp/agrishield-uploads

USER app
WORKDIR /app/backend

EXPOSE 10000

# Render injects $PORT; the shell form is required to expand it.
CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
