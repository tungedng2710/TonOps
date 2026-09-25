# Local IAM configuration

Local IAM is opt-in. Existing installations retain `fixed_users` behavior while
the flag is false.

```hocon
apiserver.auth.iam {
  enabled: true
  import_fixed_users: false
  self_signup.enabled: true
  password_policy {
    min_length: 12
    max_length: 128
    require_uppercase: false
    require_lowercase: false
    require_number: false
    require_special: false
    history: 0
    bcrypt_rounds: 12
  }
  lockout {
    max_attempts: 5
    duration_minutes: 15
  }
  audit.enabled: true
}
```

`self_signup.enabled` controls public account registration. New registrations
are always created with the `user` role. The signup request does not accept a
role field; only an authenticated administrator can grant or revoke the
`admin` role through the protected IAM user-management endpoints. Set
`CLEARML_IAM_SELF_SIGNUP_ENABLED=false` to disable public registration while
keeping local IAM enabled.

Bootstrap variables:

- `CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME`
- `CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD`, or
- `CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD_FILE`
- optional `CLEARML_IAM_BOOTSTRAP_ADMIN_DISPLAY_NAME` and
  `CLEARML_IAM_BOOTSTRAP_ADMIN_EMAIL`

Set only one password source. The file form is recommended. Bootstrap runs only
when no local administrator exists, never overwrites an account, never logs a
password, and marks the initial password for change. Remove all bootstrap
variables after the first successful start.

Usernames normalize to lowercase and accept 3-64 letters, digits, `.`, `_`, and
`-`. Password policy is always enforced by the server. bcrypt input is limited to
72 UTF-8 bytes; the configured character maximum defaults to 128.
