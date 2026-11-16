# Project artifact migration — 2026-11-10

The user explicitly requested that all project artifacts be stored on S3. This
was an operational migration of the running Compose stack; no application code,
authentication, routes, deployment configuration, or dependencies were changed.

## Completed

- Copied 327 task artifacts and 12 model files from the mounted fileserver to
  the configured RustFS bucket (1,607,549,890 bytes total).
- Downloaded each destination object and verified its SHA-256 and byte length
  against the source before updating any registered file links.
- Used conditional updates matching each original URI to avoid overwriting
  concurrent record changes. No queued or running tasks were present at preflight
  or the additional check during migration.
- Updated 79 task output destinations. All 20 projects already had the RustFS
  default; all 83 tasks present at final verification used it as well.
- Kept all 339 original fileserver source files as backups.

In the RustFS console, open the configured bucket (`tonops-artifacts`). Migrated
files use `migrated/task-artifacts/<task-id>/<artifact-id>/<filename>` and
`migrated/models/<model-id>/<filename>`. Existing S3 objects retain their paths.
ClearML artifact links now refer to the migrated objects.

## Verification and exceptions

- **PASS:** all 334 current task artifact references use S3 and return successful
  object HEAD requests; no task artifacts remain registered on the fileserver.
- **PASS:** all 339 migration sources remain present; manifest phase is complete
  with all 418 planned record updates recorded.
- **PASS:** repeat preview reports zero files and zero destinations to migrate.
- **PASS:** all 12 migrated models are included in the 15 registered S3 models
  whose objects exist.
- **Existing exception:** five model records reference `file:///root/tungn197/...`
  paths absent both on this host and in the server container. These were left
  intact. Recover the exact original files before migrating those model records.
- **Existing exception:** model `338e13cb78d944a0b03a3c1a3e48fa17` was already
  registered with an S3 key `uploading_file`; HEAD returns 404. No replacement
  object was fabricated and the record was left unchanged.
- An initial copy attempt encountered a streaming API compatibility error before
  any database updates. The read loop was corrected, then the complete copy and
  verification succeeded. The original partial-attempt manifest is retained.
- Browser downloads, SDK upload workflows, and application builds/tests were not
  run. This operation changed storage records, not application source or rendering.

## Recovery and future uploads

The completed rollback manifest is persisted in the API container at:

`/opt/clearml/config/rustfs-migration-20261110T082813481194Z.json`

This directory is mounted from `CLEARML_DATA_ROOT/config` on the host. The
executed migration procedure is saved beside it as
`rustfs-migration-20261110-executed.py`. Both files have private permissions.
The manifest records old/new URIs, old destination field presence/values,
source paths, copied sizes, SHA-256 values, and update progress.

To roll back, restore manifest fields only where their current values still
match the recorded new values; unset fields whose `old_exists` was false. Keep
S3 objects and original files until consumers have been checked. Do not blindly
restore records changed by later tasks.

Project defaults and current task destinations now use RustFS. SDK/Agent clients
still require matching S3 credentials, endpoint, and path-style addressing as
documented in the root README. Explicit client `output_uri` overrides continue
to take precedence; no global enforcement or automatic fileserver forwarding was
introduced. Check future training launchers for fileserver overrides. Dataset
state contents, pipeline parameters, logs, and debug-sample URLs were not rewritten.
