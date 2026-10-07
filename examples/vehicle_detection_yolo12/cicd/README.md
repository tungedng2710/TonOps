# YOLO12 with Gitea CI/CD

This example reuses `examples/vehicle_detection_yolo12/train.py` from TonOps.
Gitea runs the pipeline when you push to `main`, open a pull request, or manually
dispatch the workflow. A repository-scoped runner executes one job at a time.

The workflow in `.gitea/workflows/yolo12-cicd.yaml` performs these stages:

1. Check out the exact triggering commit and run the dataset, training, quality
   gate, and deployment restoration tests.
2. Train YOLO12n for one epoch on the eight-image COCO8 dataset using CPU,
   320-pixel images, batch size 2, and seed 42. This calls the same training
   function used by the existing ClearML GPU task.
3. Reject missing/nonfinite metrics or mAP50 below `0.01`, then save `best.pt`,
   `metrics.json`, and a validation image as a Gitea Actions artifact for 14 days.
   The smoke image is chosen from images the saved checkpoint detects objects in
   at the API's default confidence threshold; the metric gate uses the full
   validation split.
4. Build `tonops/yolo12-demo:<commit>` with the trained checkpoint and commit
   revision embedded in the image.
5. On `main`, deploy the image with Compose on port **7865**, check its revision
   and health, make a real image prediction, and check invalid input responses.
   A failed deployment restores the preceding image; a failed first deployment
   removes the demo service. Pull requests test/train/build without deploying.

COCO8 and the low mAP50 gate are for checking pipeline mechanics. Use a separate
held-out dataset and a project-specific accuracy gate before deploying a model
for real use. This demo has 80 COCO classes; it is not a trained vehicle model.
Training does not require TonOps API credentials or a ClearML GPU worker.
The original ClearML GPU workflow remains available in `project.py`.

## Set up from the TonOps stack repository

Start Gitea using the stack's root `compose.yaml` and create your Gitea account.
Then, from the full TonOps repository root:

```bash
python3 scripts/setup-gitea-yolo12.py --username tungn197
```

The script prompts for your password, builds `tonops/yolo12-ci:local`, creates the
private `tungn197/yolo12-cicd-example` repository, enables Actions, registers the
repository runner, starts it using `compose.cicd.yaml`, and pushes a source-only
snapshot. It copies an explicit set of example code and tests; it excludes local
credentials, datasets, model weights, and stack data. It leaves the TonOps Git
working tree and its existing remote intact.

Credentials are held in memory for API/Git requests. The runner identity is
stored privately at `CLEARML_DATA_ROOT/gitea-runner/.runner`; its temporary
registration token file is deleted after registration. No account password or
registration token is stored in the workflow. Runner setup follows the
[official Docker runner documentation](https://docs.gitea.com/runner/2/installation/docker/).
The runner can access this host's Docker daemon to build and deploy images, so
keep it scoped to this private repository and run trusted code.

On this host the runner and its job containers use host networking so they can
reach Gitea's `http://localhost:7864` URL and the deployed model's published port.
For another Gitea hostname use `--url http://YOUR_HOST:7864` and configure that
reachable hostname in Gitea. The runner is intended to run on this Linux stack
host. Set `GITEA_RUNNER_IMAGE` in `.env` to override its image.

## View and rerun the pipeline

- Repository: <http://localhost:7864/tungn197/yolo12-cicd-example>
- Runs and downloadable model artifacts: <http://localhost:7864/tungn197/yolo12-cicd-example/actions>
- Deployed model health and metrics: <http://localhost:7865/health>
- Interactive prediction API: <http://localhost:7865/docs>

Push a new commit to `main` to trigger another deployment. For local TonOps
example changes, run the setup script again with `--skip-build` to publish the
updated snapshot. It uses a normal Git push and stops if the example repository
has diverged; it never force-pushes. If the snapshot is unchanged, rerun a job
from Gitea Actions or use the workflow's **Run workflow** button. Rebuild the CI
image by omitting `--skip-build` after changing its Dockerfile or dependencies.

To edit only the dedicated example repository:

```bash
git clone http://localhost:7864/tungn197/yolo12-cicd-example.git
cd yolo12-cicd-example
# Make changes, then commit and push to main using your Gitea credentials.
```

Once downloaded from a run's artifact, predict with the included sample image:

```bash
curl -f http://localhost:7865/health
curl -f http://localhost:7865/predict -F file=@sample.jpg
```

The prediction API accepts uploaded images up to 8 MiB and 20 million pixels.
Its default confidence is `0.1` for this one-epoch smoke model.
An optional `confidence` query parameter must be greater than 0 and at most 1.
Responses contain the deployed revision and class labels, confidence scores,
and pixel-coordinate bounding boxes. The demo endpoint has no authentication.

## Operate from the stack repository

```bash
docker compose -f compose.yaml -f compose.cicd.yaml ps gitea_runner
docker compose -f compose.yaml -f compose.cicd.yaml logs -f gitea_runner
docker compose -f compose.yaml -f compose.cicd.yaml up -d gitea_runner
```

The optional runner overlay is separate from `restart_all.sh`. To inspect or
stop the serving stack, use its Compose file and the image from a successful run:

```bash
export YOLO12_IMAGE=tonops/yolo12-demo:COMMIT_SHA
docker compose -f examples/vehicle_detection_yolo12/cicd/compose.yaml ps
docker compose -f examples/vehicle_detection_yolo12/cicd/compose.yaml logs detector
docker compose -f examples/vehicle_detection_yolo12/cicd/compose.yaml down
```

Serving images are kept locally by commit. To restore a particular successful
version, set `YOLO12_IMAGE` to that image and run Compose `up -d --wait`.
