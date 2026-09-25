# Local IAM security notes

- Passwords use bcrypt with a configurable cost (12 by default). Plaintext and
  hashes are excluded from API responses and audit metadata.
- Unknown users and bad passwords return the same error. Unknown-user checks also
  execute bcrypt work to reduce timing differences.
- Five failed attempts lock an account for 15 minutes by default. Successful login
  clears the counter and records time/IP.
- Admin endpoint access is enforced by server schema role allowlists. UI menu
  hiding and route guards are convenience controls only.
- Request schemas reject additional properties. Services build Mongo queries only
  from explicit fields and sort allowlists, preventing operator injection and mass
  assignment.
- A Redis distributed lock serializes last-active-admin checks. The last active
  admin cannot be disabled, deleted, or downgraded.
- `auth_version` invalidates stateless JWTs after status, role, or password changes.
  Deleted-user tokens fail because their database identity no longer exists.
- The password-change response replaces the current cookie with a new versioned
  token. Admin resets do not disclose plaintext unless the server generated a
  temporary password; that value is returned exactly once.
- IAM audit is append-only through the API. There is no delete endpoint or UI.
- Existing cookie CSRF posture is preserved (`HttpOnly`, configurable `Secure`,
  and `SameSite`). Production deployments should terminate TLS and set the cookie
  `secure` option.

Known MVP boundary: roles govern IAM administration, while projects, tasks,
datasets, models, queues, and agents remain in the shared ClearML workspace.
LDAP/OIDC, MFA, service accounts, API-key lifecycle UI, session enumeration, and
resource ACLs are deferred.
