ARG SERVING_BASE_IMAGE=tonops/yolo12-demo:9df0e0c370dd6f43d395a6e1258a80792091ca63
FROM ${SERVING_BASE_IMAGE}
USER root
RUN python -m pip install --no-cache-dir clearml==2.1.12
COPY serve.py /opt/yolo-serving/serve.py
WORKDIR /opt/yolo-serving
ENV YOLO_AUTOINSTALL=false PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    YOLO_CONFIG_DIR=/tmp/ultralytics MPLCONFIGDIR=/tmp/matplotlib OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
USER detector
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
