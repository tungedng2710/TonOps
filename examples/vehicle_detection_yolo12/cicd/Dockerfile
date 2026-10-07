# Build with examples/vehicle_detection_yolo12 as the context.
FROM docker:28-cli AS docker-cli
FROM node:20-bookworm-slim AS node-cli

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLBACKEND=Agg \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    OMP_NUM_THREADS=2 \
    MKL_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY cicd/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir torch==2.7.1 torchvision==0.22.1 \
        --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -r /tmp/requirements.txt \
    && python -m pip check
WORKDIR /opt/yolo12
# Unsupported uploads must not install optional codecs while serving requests.
ENV YOLO_AUTOINSTALL=false

FROM runtime AS ci
RUN apt-get update && apt-get install -y --no-install-recommends git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
COPY --from=node-cli /usr/local/bin/node /usr/local/bin/node

FROM runtime AS serving
ARG MODEL_REVISION=local
ENV MODEL_REVISION=${MODEL_REVISION} MODEL_PATH=/opt/yolo12/model/best.pt
LABEL org.opencontainers.image.revision=${MODEL_REVISION}
COPY cicd/serve.py /opt/yolo12/serve.py
COPY cicd/build/best.pt cicd/build/metrics.json /opt/yolo12/model/
RUN useradd --uid 1000 --create-home detector \
    && mkdir -p /tmp/ultralytics \
    && chown -R detector:detector /tmp/ultralytics
USER detector
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
