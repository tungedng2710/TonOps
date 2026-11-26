ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/mlops
COPY requirements.lock .
RUN python -m pip install --no-cache-dir --only-binary=:all: --require-hashes -r requirements.lock \
    && python -m pip check \
    && install -d -o 10001 -g 10001 /results
RUN useradd --create-home --uid 10001 --user-group mlops
COPY init-db.py check-mlflow.py ./
COPY --chmod=755 start-mlflow.sh ./
USER 10001:10001
