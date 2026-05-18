FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    LOCAL_MODE=false \
    WORK_DIR=/tmp/ver2

WORKDIR /app

# System fonts for visualization.py (confusion matrix PNG rendering)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "scripts/run_cloud_pipeline.py"]
