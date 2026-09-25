# Migrating `fixed_users`

The default is non-destructive: with IAM disabled, ClearML uses the unchanged
fixed-user path. To import:

1. Back up MongoDB and retain `apiserver.conf`.
2. Enable both `apiserver.auth.iam.enabled` and
   `apiserver.auth.iam.import_fixed_users` for one startup.
3. Start the API server and review one username-only log entry per imported user.
4. Bootstrap or promote at least one administrator through IAM.
5. Set `import_fixed_users=false`; after login validation, remove or disable the
   old fixed-user configuration.

Usernames are normalized to lowercase. Existing base64-encoded bcrypt hashes are
decoded and reused without exposing plaintext. Legacy plaintext fixed-user
passwords are immediately bcrypt-hashed and accounts are marked to change their
password. Guest users are not imported. Import is idempotent: an existing username
is skipped.

If usernames differ only by case, resolve the collision in configuration before
import. Email remains optional for imported local accounts. Disabling IAM later
returns authentication to the original fixed-user behavior and does not erase IAM
data.
