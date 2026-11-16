# YOLO endpoints for tungn197 — 2026-11-10

Three existing owned checkpoints are now served by the independent
`tonops-yolo-serving-inference-1` container, image `tonops/yolo-serving:local`.
The service is healthy and uses `restart: unless-stopped`. The configured SDK
account was verified as Tung Nguyen, user `030b21c6dc424bffaefda73e0739d186`.

| Model | Registry ID | JSON prediction URL |
| --- | --- | --- |
| YOLO11n, smoke-yolo11-best | `1f387bfd6e134e3a9243edf1d29cf266` | `http://27.66.108.30:7872/predict/yolo11` |
| YOLO12n, smoke-yolo12-best | `4bb1f4284ac345caaa3199c65432b775` | `http://27.66.108.30:7872/predict/yolo12` |
| YOLO26n, smoke-yolo26-best | `236080f00cb743a09df6cf9226fea405` | `http://27.66.108.30:7872/predict/yolo26` |

Find them in [Model endpoints](http://27.66.108.30:7861/endpoints/active).
The [interactive API docs](http://27.66.108.30:7872/docs) support image uploads.
`/health` reports loaded IDs and heartbeat freshness; `/models` lists URLs.
Model metadata also contains `serving_endpoint`, `serving_docs` and
`serving_input`. Source model URIs, Draft status, tags and training tasks were
preserved. These are smoke-training checkpoints, not production-accuracy claims.

Upload a JPEG/PNG to the multipart endpoint:

```bash
curl -F 'file=@/path/to/image.jpg' \
  http://27.66.108.30:7872/predict/yolo12/image
```

Or use the existing base64-JSON client:

```bash
python examples/call_yolo12_endpoint.py /path/to/image.jpg
python examples/call_yolo12_endpoint.py /path/to/image.jpg \
  --endpoint http://27.66.108.30:7872/predict/yolo11
```

Prediction routes are unauthenticated, following the existing demo's trusted
network deployment pattern. The service authenticates to ClearML with the
account's existing SDK API credentials, stored only in a private mode-0600 file
under ignored `docker-data`, mounted read-only and excluded from the image.
No password, credentials or tokens are committed. No IAM, CORS or app auth settings
were changed. Runtime package auto-installation is disabled.

The service uses the existing CPU YOLO runtime (two CPU cores, 3 GiB limit).
Weights were fetched through registered RustFS URLs and their SHA-256 values
match the original training checkpoint files. Hashes and immutable model IDs
are recorded in `docker-data/examples/yolo-serving/models.json` and rechecked
on startup. The API verifies account ownership and the registered URI before
loading; all three models execute a warmup before registration.

Every 15 seconds the service reports actual request counts, request rate, uptime
and latency through native ClearML serving APIs. Endpoint references point to
the actual registry IDs. Registrations expire after 120 seconds without reports;
shutdown unregisters this service's endpoints.

Verification performed:

- Real remote JSON and multipart predictions on all three models: PASS. The
  bundled bus image produced 6, 5 and 7 detections respectively at confidence 0.1.
  First JSON call latency was approximately 690, 688 and 501 ms on CPU; these are
  single smoke requests, not a throughput benchmark or accuracy evaluation.
- Invalid base64/image, unknown model and invalid confidence return HTTP
  400/400/404/422: PASS. Size/missing-length validation is covered by unit tests.
- The existing `examples/call_yolo12_endpoint.py` client: PASS, 5 detections.
- Service restart, three-model recovery and fresh native heartbeat reports: PASS.
  Repeated actual inference after restart and confirmed nonzero request/latency
  values for all three endpoints in ClearML.
- Five focused contract tests in the configured host environment: PASS.
- The same five tests inside the actual serving image with networking disabled:
  PASS; `pip check` reports no broken requirements.
- Normal tungn197 username/password login and browser verification: PASS. All
  three live endpoint rows and YOLO12 endpoint details are visible, with no
  unexpected browser runtime errors.
- `git diff --check`, Python compilation and deployment build: PASS.
- Full backend/frontend suites were not rerun: this deployment does not modify
  their source or configuration. Concurrent-load/long-duration soak tests and
  production accuracy evaluation were not performed.

The initial diagnostic HEAD request to a GET-presigned storage URL returned 403;
correct streaming GET downloads passed. An initial host invalid-image test
triggered Ultralytics' optional codec installation; that package was removed,
automatic installation disabled and tests rerun successfully.

Operate from the repository root:

```bash
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml ps
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml logs --tail 100 inference
docker compose --env-file docker-data/examples/yolo-serving/deployment.env \
  -f examples/yolo_serving/compose.yaml restart inference
```

Use `down` with the same file arguments to stop this inference service. Models
and original storage objects remain. Preparation/redeployment instructions are
in [the serving README](../examples/yolo_serving/README.md).

Temporary verification artifacts: `/tmp/tonops-yolo-serving-live-results.json`,
`/tmp/tonops-yolo-serving-active-endpoints.json`,
`/tmp/tonops-yolo-serving-client-result.json`,
`/tmp/tonops-yolo-serving-{build,tests,container-tests,prepare,start,restart}.log`
and `/tmp/tonops-yolo-serving-browser/` screenshots/results.
