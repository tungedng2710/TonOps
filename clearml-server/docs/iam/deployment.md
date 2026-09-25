# Air-gapped IAM deployment and upgrade

Build the modified `clearml-server` and `clearml-web` images inside the connected
build zone, scan them, then mirror the images and package caches into the LAN.
Runtime IAM makes no external HTTP, identity-provider, font, avatar, telemetry, or
CAPTCHA requests.

The upstream web application does contain unrelated outbound references: the
update checker posts to `https://updates.clear.ml`, the welcome-video component
can load YouTube's iframe API, header/help/legal links target public sites, and
the report-widgets development environment contains hosted ClearML URLs. Plotly,
Ace, icons, and IAM assets in the normal OSS build are local. For a strict
air-gap, block outbound traffic at the proxy/firewall, hide update/tutorial
features in the web configuration, and build report widgets with LAN endpoints.
These failures do not affect local IAM, but the upstream update checker may log a
failed request while outbound networking is blocked.

1. Back up the MongoDB auth/backend databases and Redis configuration.
2. Deploy the server and web images from this fork while IAM remains disabled.
3. Put a bootstrap password in a root-readable file under the mounted ClearML
   config directory, for example `/opt/clearml/config/iam-admin-password`.
4. Set `CLEARML_IAM_ENABLED=true`, the bootstrap username, and
   `CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE` to the container-visible path.
5. Run `docker compose up -d` and verify the bootstrap completion message contains
   only the username.
6. Remove the bootstrap variables/file, restart the API server, log in, and change
   the temporary password.
7. Verify Settings > User Management and run the login/disable/audit smoke test.

MongoDB remains on the existing persistent `/opt/clearml/data/mongo_4` volume.
MongoEngine creates sparse/compound indexes on startup. The unique username index
is sparse, so legacy service users without usernames remain valid. On very large
auth databases, create the indexes during a maintenance window before enabling
IAM to avoid foreground index-build impact.

Rollback is configuration-only: set IAM disabled and restart. Existing fixed-user
configuration is untouched. IAM collections and fields may remain in MongoDB and
are ignored while disabled; do not drop them if a later rollback reversal is
possible.

The supplied Linux Compose files pass the IAM flag and bootstrap variables to the
API server. The password-file path must refer to a file already available through
the `/opt/clearml/config` mount. Never bake the password into an image or commit it
to Compose.
