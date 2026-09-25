# Local IAM architecture

## Existing OSS authentication flow

The web login form sends HTTP Basic credentials to `auth.login`. The API server
authorizes Basic credentials in `apiserver/service_repo/auth/auth.py`, resolves an
auth-database `User`, and `AuthBLL.get_token_for_user` returns the normal ClearML
JWT in an HTTP-only cookie. Subsequent calls are decoded by `Token` and exposed as
`call.identity`. Endpoint role allowlists come from HOCON files under
`apiserver/schema/services`.

`FixedUser` reads `apiserver.auth.fixed_users`, and startup initialization mirrors
those entries into the auth and backend user collections. ClearML Web discovers
password mode using `login.supported_modes`, keeps current-user state in the NgRx
users reducer, and uses standalone Angular routes/components under Settings.

## IAM extension

```text
ClearML Web
    |
    v
ClearML API (iam.* service/actions)
    |
    v
LocalDatabaseProvider / IAM service
    |
    +--> auth.users
    +--> iam_groups
    +--> iam_group_members
    +--> iam_audit
    |
    v
MongoDB auth database
```

The extension reuses Basic login, the HTTP-only cookie, JWT identity, endpoint
schema validation, role allowlists, MongoEngine, and the existing backend user
mirror. It does not add an authentication protocol or database.

Local users add username/password/status/lockout fields to the existing auth user
document. Groups and audit records use separate collections. Only `admin`, `root`,
and internal `system` identities may invoke management endpoints; `iam.me` and
`iam.change_password` allow every authenticated role.

`auth_version` is embedded in local-user JWTs and checked against MongoDB on every
request. Disable, delete, password change/reset, and role changes therefore revoke
all older tokens immediately. Explicit logout continues to use ClearML's Redis
session revocation.

The model intentionally leaves resource permissions out of scope. A future ACL
layer can use users and groups as subjects without changing authentication.
