#!/usr/bin/env python3
"""Run two real ClearML pipelines and keep their prediction endpoints online."""

import argparse
import getpass
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests


def prepare(dataset):
    from sklearn.datasets import load_iris, load_wine
    from sklearn.model_selection import train_test_split

    data = {"iris": load_iris, "wine": load_wine}[dataset]()
    x_train, x_test, y_train, y_test = train_test_split(
        data.data, data.target, test_size=0.25, random_state=42, stratify=data.target
    )
    return (x_train, x_test, y_train, y_test, list(data.target_names))


def train(data):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, random_state=42))
    model.fit(data[0], data[2])
    return model


def evaluate(data, model, publish=True):
    import tempfile
    from pathlib import Path
    import joblib
    from sklearn.metrics import accuracy_score, confusion_matrix

    predictions = model.predict(data[1])
    accuracy = float(accuracy_score(data[3], predictions))
    if publish:
        from clearml import OutputModel, Task

        task = Task.current_task()
        task.get_logger().report_scalar("evaluation", "accuracy", accuracy, iteration=0)
        task.get_logger().report_confusion_matrix(
            "evaluation", "confusion matrix", matrix=confusion_matrix(data[3], predictions),
            xlabels=data[4], ylabels=data[4], iteration=0,
        )
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "model.joblib")
            joblib.dump({"model": model, "labels": data[4]}, filename)
            output = OutputModel(task=task, name=task.name, framework="ScikitLearn")
            output.update_weights(filename)
            output.wait_for_uploads()
            output.publish()
            return {"accuracy": accuracy, "model_id": output.id}
    return {"accuracy": accuracy}


class Api:
    def __init__(self, url, username, password):
        self.url = url.rstrip("/")
        self.session = requests.Session()
        response = self.session.post(
            self.url + "/auth.login", auth=(username, password), json={}, timeout=15
        )
        response.raise_for_status()
        self.token = response.json()["data"]["token"]
        self.session.headers["Authorization"] = "Bearer " + self.token

    def call(self, action, payload):
        response = self.session.post(self.url + "/" + action, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()
        if result.get("meta", {}).get("result_code", 200) != 200:
            raise RuntimeError(f"{action}: {result.get('meta')}")
        return result["data"]


def run_pipeline(dataset, output_uri):
    from clearml import PipelineController, Task

    pipe = PipelineController(
        name=f"{dataset.title()} classification", project="Examples", version="1.0.0",
        pool_frequency=0.05, add_pipeline_tags=True, output_uri=output_uri,
    )
    pipe.add_parameter("dataset", dataset)
    common = {"packages": ["clearml", "scikit-learn", "joblib"], "output_uri": output_uri}
    pipe.add_function_step(
        name="prepare", function=prepare, function_kwargs={"dataset": "${pipeline.dataset}"},
        function_return=["data"], task_type="data_processing", **common,
    )
    pipe.add_function_step(
        name="train", function=train, function_kwargs={"data": "${prepare.data}"},
        function_return=["model"], task_type="training", **common,
    )
    pipe.add_function_step(
        name="evaluate", function=evaluate,
        function_kwargs={"data": "${prepare.data}", "model": "${train.model}"},
        function_return=["result"], task_type="testing", **common,
    )
    try:
        pipe.start_locally(run_pipeline_steps_locally=True)
        if not pipe.is_successful():
            raise RuntimeError(f"{dataset} pipeline failed; inspect its run in ClearML")
        node = pipe.get_pipeline_dag()["evaluate"]
        result = Task.get_task(task_id=node.executed).artifacts["result"].get()
        return result
    finally:
        pipe.stop()


class PredictionServer(ThreadingHTTPServer):
    def __init__(self, address, models):
        super().__init__(address, PredictionHandler)
        self.models = models
        self.stats = {name: {"requests": 0, "latency_ms": 0} for name in models}
        self.stats_lock = threading.Lock()


class PredictionHandler(BaseHTTPRequestHandler):
    def reply(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "unknown route"})
        self.reply(200, {"status": "ok", "models": list(self.server.models)})

    def do_POST(self):
        import numpy as np

        dataset = self.path.removeprefix("/predict/")
        if self.path != f"/predict/{dataset}" or dataset not in self.server.models:
            return self.reply(404, {"error": "unknown model"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 1_000_000:
                raise ValueError("body must be between 1 and 1000000 bytes")
            values = np.asarray(json.loads(self.rfile.read(length))["instances"], dtype=float)
            bundle = self.server.models[dataset]
            if values.ndim != 2 or not 1 <= len(values) <= 1000:
                raise ValueError("instances must contain 1 to 1000 feature rows")
            if values.shape[1] != bundle["model"].n_features_in_ or not np.isfinite(values).all():
                raise ValueError("invalid feature count or non-finite values")
            started = time.monotonic()
            predictions = bundle["model"].predict(values).tolist()
            probabilities = bundle["model"].predict_proba(values).tolist()
            with self.server.stats_lock:
                self.server.stats[dataset]["requests"] += 1
                self.server.stats[dataset]["latency_ms"] = round((time.monotonic() - started) * 1000)
            self.reply(200, {"predictions": predictions, "labels": [bundle["labels"][i] for i in predictions],
                             "probabilities": probabilities})
        except (ValueError, TypeError, KeyError) as error:
            self.reply(400, {"error": str(error)})

    def log_message(self, *_):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:7862")
    parser.add_argument("--web-url", default="http://localhost:7861")
    parser.add_argument("--files-url", default="http://localhost:7863")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7870)
    parser.add_argument("--public-url", default="http://localhost:7870")
    parser.add_argument("--self-check", action="store_true", help="verify training without a server")
    args = parser.parse_args()
    if args.self_check:
        for name in ("iris", "wine"):
            data = prepare(name)
            print(name, evaluate(data, train(data), publish=False))
        return

    api = Api(args.api_url, args.username, os.environ.get("EXAMPLES_PASSWORD") or getpass.getpass("Admin password: "))
    os.environ.update(CLEARML_API_HOST=args.api_url, CLEARML_WEB_HOST=args.web_url,
                      CLEARML_FILES_HOST=args.files_url, CLEARML_AUTH_TOKEN=api.token)
    import joblib
    from clearml import Model, StorageManager

    # Bind before creating server records, so an occupied port fails without creating runs.
    server = PredictionServer((args.bind, args.port), {})
    registered = []
    serving = False
    try:
        for dataset in ("iris", "wine"):
            result = run_pipeline(dataset, args.files_url)
            model = Model(model_id=result["model_id"])
            bundle = joblib.load(StorageManager.get_local_copy(model.url))
            server.models[dataset] = bundle
            server.stats[dataset] = {"requests": 0, "latency_ms": 0}
            registered.append({
                "container_id": f"examples-{dataset}-{args.port}", "endpoint_name": f"{dataset.title()} classifier",
                "endpoint_url": args.public_url.rstrip("/") + f"/predict/{dataset}",
                "model_name": f"{dataset.title()} Logistic Regression", "model_version": "1.0.0",
                "model_source": "ScikitLearn", "input_type": "float64", "input_size": str(bundle["model"].n_features_in_),
                "tags": ["example", dataset], "reference": [{"type": "model", "value": model.id}],
            })
            print(f"{dataset}: accuracy={result['accuracy']:.3f}, model={model.id}", flush=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        serving = True
        started = time.monotonic()
        previous = {name: 0 for name in server.models}
        for entry in registered:
            api.call("serving.register_container", dict(entry, timeout=120))
            print(entry["endpoint_url"], flush=True)
        print("Endpoints online. Press Ctrl+C to stop and unregister.", flush=True)
        while True:
            for entry in registered:
                dataset = entry["tags"][1]
                with server.stats_lock:
                    stats = dict(server.stats[dataset])
                api.call("serving.container_status_report", dict(
                    entry, uptime_sec=int(time.monotonic() - started), requests_num=stats["requests"],
                    requests_min=(stats["requests"] - previous[dataset]) * 2, latency_ms=stats["latency_ms"],
                ))
                previous[dataset] = stats["requests"]
            time.sleep(30)
    except KeyboardInterrupt:
        pass
    finally:
        if serving:
            server.shutdown()
        for entry in registered:
            try:
                api.call("serving.unregister_container", {"container_id": entry["container_id"]})
            except requests.RequestException:
                pass  # Registration expires after 120 seconds if the API is unavailable.
        server.server_close()


if __name__ == "__main__":
    main()
