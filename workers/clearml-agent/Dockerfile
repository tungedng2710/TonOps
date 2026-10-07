FROM pytorch/pytorch:2.7.1-cuda12.6-cudnn9-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-task.txt /tmp/requirements-task.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-task.txt \
    && python -m pip check

ENV MPLBACKEND=Agg
