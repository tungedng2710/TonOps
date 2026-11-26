"""Train on local synthetic data and verify a persisted MLflow model."""

import argparse
import hashlib
import json
import os
import platform
import socket
import tempfile
from importlib.metadata import version
from pathlib import Path

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split

SEED = 7871
FEATURES = ["x1", "x2", "x3"]
REPORT = "evaluation.json"
ALIAS = "candidate"
SAMPLES = pd.DataFrame([[3.0, 0.0, -2.0], [-3.0, 0.0, 2.0]], columns=FEATURES)
MODEL_PACKAGES = ("mlflow", "scikit-learn", "skops", "numpy", "pandas", "scipy")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def proxy_path(uri: str) -> str:
    prefix = "mlflow-artifacts:/"
    require(uri.startswith(prefix) and not uri.startswith(prefix + "/"), f"Expected proxy URI, got {uri}")
    return uri.removeprefix(prefix).rstrip("/")


def train(name: str, reference: Path, lockfile: Path) -> None:
    features = pd.DataFrame(np.random.default_rng(SEED).normal(size=(1024, 3)), columns=FEATURES)
    labels = (features.x1 + 0.4 * features.x2 - 0.6 * features.x3 > 0).astype("int64")
    training, testing = train_test_split(
        features.assign(label=labels), test_size=0.25, random_state=SEED, stratify=labels,
    )
    parameters = {"C": 1.0, "max_iter": 200, "random_state": SEED}
    classifier = LogisticRegression(**parameters).fit(training[FEATURES], training["label"])
    predictions = classifier.predict(testing[FEATURES])
    accuracy = float(accuracy_score(testing["label"], predictions))
    require(accuracy >= 0.95, f"Unexpected held-out accuracy {accuracy}")
    requirements = {package: version(package) for package in MODEL_PACKAGES}
    report = {
        "accuracy": accuracy,
        "confusion_matrix": confusion_matrix(testing["label"], predictions).tolist(),
        "training_rows": len(training),
        "test_rows": len(testing),
        "seed": SEED,
        "python": platform.python_version(),
        "platform": platform.machine(),
        "requirements_lock_sha256": hashlib.sha256(lockfile.read_bytes()).hexdigest(),
        "packages": requirements,
    }
    experiment = mlflow.set_experiment(name)
    proxy_path(experiment.artifact_location)
    with mlflow.start_run(run_name="synthetic-logistic-regression") as run:
        mlflow.log_params(parameters)
        mlflow.log_input(
            mlflow.data.from_pandas(training, name="synthetic-train", targets="label"),
            context="training",
        )
        mlflow.log_input(
            mlflow.data.from_pandas(testing, name="synthetic-test", targets="label"),
            context="test",
        )
        mlflow.log_dict(report, REPORT)
        model = mlflow.sklearn.log_model(
            classifier,
            name="classifier",
            signature=infer_signature(SAMPLES, classifier.predict(SAMPLES)),
            input_example=SAMPLES,
            serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_SKOPS,
            pip_requirements=[f"{package}=={number}" for package, number in requirements.items()],
        )
        mlflow.log_metric("accuracy", accuracy, model_id=model.model_id)
    registered = mlflow.register_model(model.model_uri, name, await_registration_for=30)
    client = MlflowClient()
    client.set_registered_model_alias(name, ALIAS, registered.version)
    logged = client.get_logged_model(model.model_id)
    result = {
        "experiment_id": experiment.experiment_id,
        "run_id": run.info.run_id,
        "model_id": model.model_id,
        "model_name": name,
        "model_version": registered.version,
        "run_artifact_key": f"{proxy_path(run.info.artifact_uri)}/{REPORT}",
        "model_artifact_key": f"{proxy_path(logged.artifact_location)}/MLmodel",
        "accuracy": accuracy,
    }
    with tempfile.NamedTemporaryFile(mode="w", dir=reference.parent, delete=False) as handle:
        json.dump(result, handle, indent=2)
        staged_path = Path(handle.name)
    staged_path.replace(reference)
    print(json.dumps(result, indent=2))


def verify(reference: Path) -> None:
    result = json.loads(reference.read_text())
    client = MlflowClient()
    run = client.get_run(result["run_id"])
    require(run.info.status == "FINISHED", "Run is not finished")
    require(run.info.experiment_id == result["experiment_id"], "Experiment ID mismatch")
    require(run.data.metrics["accuracy"] == result["accuracy"], "Tracked accuracy differs")
    require(run.data.params["random_state"] == str(SEED), "Tracked parameters differ")
    contexts = {
        tag.value for item in run.inputs.dataset_inputs for tag in item.tags
        if tag.key == "mlflow.data.context"
    }
    require(contexts == {"training", "test"}, f"Unexpected dataset contexts {contexts}")

    with tempfile.TemporaryDirectory() as directory:
        report = mlflow.artifacts.download_artifacts(
            run_id=run.info.run_id, artifact_path=REPORT, dst_path=directory,
        )
        require(json.loads(Path(report).read_text())["accuracy"] == result["accuracy"],
                "Downloaded evaluation report differs")

    model_name = result["model_name"]
    version_number = result["model_version"]
    registered = client.get_model_version(model_name, version_number)
    logged = client.get_logged_model(result["model_id"])
    require(registered.run_id == run.info.run_id == logged.source_run_id
            and registered.source == f"models:/{logged.model_id}",
            "Registry version has incorrect run or logged model lineage")
    require(registered.status == "READY", "Registry version is not ready")
    require(client.get_model_version_by_alias(model_name, ALIAS).version == version_number,
            "Registry candidate alias points to a different version")
    for uri in (f"models:/{model_name}/{version_number}", f"models:/{model_name}@{ALIAS}"):
        model = mlflow.pyfunc.load_model(uri)
        require(model.metadata.signature is not None and model.metadata.saved_input_example_info is not None,
                "Model signature or input example missing")
        require(np.asarray(model.predict(SAMPLES)).tolist() == [1, 0], f"Unexpected predictions from {uri}")
    print(f"Verified run {run.info.run_id}, artifact, and {model_name} v{version_number} via exact version and @{ALIAS}")


def verify_client_isolation(storage_ip: str) -> None:
    forbidden = {"MLFLOW_S3_ENDPOINT_URL", "MLFLOW_ARTIFACTS_DESTINATION"}
    require(not any(name.startswith("AWS_") and name != "AWS_EC2_METADATA_DISABLED"
                    or name in forbidden for name in os.environ), "Tracking client received S3 settings")
    require(not Path("/run/secrets").exists(), "Tracking client received secret mounts")
    try:
        socket.getaddrinfo("rustfs", 9000)
    except socket.gaierror:
        pass
    else:
        raise RuntimeError("Tracking client can resolve the private RustFS service")

    try:
        with socket.create_connection((storage_ip, 9000), timeout=2):
            pass
    except OSError:
        print("Tracking client has no S3 credentials, RustFS DNS entry, or direct TCP route")
    else:
        raise RuntimeError("Tracking client can reach the private RustFS service by IP")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["train", "verify", "check-isolation"])
    parser.add_argument("--name", default="mlops-sklearn-demo")
    parser.add_argument("--reference", type=Path, default=Path("/results/demo.json"))
    parser.add_argument("--lockfile", type=Path, default=Path("/opt/mlops/requirements.lock"))
    parser.add_argument("--storage-ip", help="Private RustFS IP for the isolation test")
    args = parser.parse_args()
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    require(tracking_uri.startswith(("http://", "https://")), "Set MLFLOW_TRACKING_URI to the tracking server")
    if args.action == "train":
        train(args.name, args.reference, args.lockfile)
    elif args.action == "verify":
        verify(args.reference)
    else:
        if not args.storage_ip:
            parser.error("check-isolation requires --storage-ip")
        verify_client_isolation(args.storage_ip)


if __name__ == "__main__":
    main()
