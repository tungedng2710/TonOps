# Coding Agent Prompt — Add IAM and User Management Web App to ClearML OSS

You are a senior software architect and full-stack engineer responsible for forking and extending ClearML OSS to add an internal IAM and User Management system for a fully air-gapped deployment.

## 1. Context

We use ClearML as the internal MLOps platform for the IVA system.

The deployment runs entirely inside a private LAN with no Internet access.

Main components:

```text
ClearML Server
├── Web App
├── API Server
├── File Server
├── MongoDB
├── Elasticsearch
└── Redis

ClearML Agents
├── GPU workers
└── CPU workers

Internal services
├── Gitea
├── MinIO
├── Harbor
└── Internal PyPI
```

ClearML is responsible for managing:

- Projects
- Experiments / Tasks
- Metrics
- Logs
- Datasets
- Models
- Model Registry
- Pipelines
- Queues
- Agents
- Artifacts

ClearML OSS currently supports a `fixed_users` mechanism, but it does not provide the User Management UI and IAM/RBAC capabilities required for this deployment.

The goal of this fork is to add **fully local IAM** without depending on ClearML Cloud, Auth0, SaaS services, or any Internet-hosted authentication provider.

---

## 2. Repositories

Work on the two open-source repositories:

```text
clearml/clearml-server
clearml/clearml-web
```

Backend:

```text
clearml-server
```

Frontend:

```text
clearml-web
```

Do not use or copy any proprietary or Enterprise ClearML source code.

You may only:

- inspect the OSS source code;
- read public documentation and APIs;
- extend the OSS implementation;
- implement a new IAM solution independently.

If a feature exists only in ClearML Enterprise, you may use publicly documented behavior as a functional reference, but the implementation must be original and based only on OSS code and public documentation.

---

## 3. Main Goal

Add database-backed user management directly to ClearML OSS.

An administrator must be able to use:

```text
ClearML Web
    |
    └── Settings
          |
          └── User Management
                ├── Users
                ├── Groups
                └── Audit Log
```

MVP functionality:

```text
User Management
├── Create user
├── Edit user
├── Disable user
├── Enable user
├── Reset password
├── Change own password
├── Delete or deactivate user
├── Admin/User role
├── User groups
├── Add/remove users from groups
├── Last login
└── Audit log
```

All IAM data must remain local.

Do not depend on:

```text
ClearML Cloud
Auth0
Firebase
Google OAuth
Microsoft OAuth
AWS Cognito
external SaaS
```

---

## 4. Important: Start by Reading the Existing Source

Before making any code changes, inspect both repositories carefully.

Determine:

1. Where ClearML Server currently handles login.
2. Where `auth.fixed_users` is parsed.
3. Where password verification happens.
4. Where JWT/access tokens are generated.
5. How user identity is encoded in the token.
6. How the current user/request context is created.
7. ClearML Server API endpoint conventions.
8. The database abstraction/data access layer used by the backend.
9. Existing MongoDB collections or schemas related to users/authentication.
10. How ClearML Web performs login.
11. How ClearML Web stores the current-user state.
12. Angular routing/menu/settings structure.
13. HTTP service/API client patterns.
14. Error handling patterns.
15. Existing backend and frontend test frameworks.

Do not rewrite the authentication stack if ClearML already has a suitable token/session infrastructure.

Prefer:

```text
reuse existing login/token infrastructure
```

and replace the source of user data from:

```text
fixed_users config
```

to:

```text
database-backed users
```

---

## 5. Target Architecture

```text
                         ClearML Web
                             |
                             |
                  username / password
                             |
                             v
                    ClearML API Server
                             |
                     IAM / Auth Service
                             |
              +--------------+--------------+
              |                             |
              v                             v
           Users                          Groups
              |                             |
              +--------------+--------------+
                             |
                             v
                          MongoDB
```

Authentication flow:

```text
Browser
   |
   | username/password
   v
POST login
   |
   v
IAM User Lookup
   |
   v
Password Verify
   |
   v
status == ACTIVE ?
   |
   v
ClearML JWT/token generation
   |
   v
ClearML Web
```

Preserve existing ClearML token semantics as much as possible.

Do not introduce an incompatible authentication protocol unless absolutely necessary.

---

## 6. User Data Model

Design a schema equivalent to:

```text
User
--------------------------------
id
username
email
display_name

password_hash

role
    ADMIN
    USER

status
    ACTIVE
    DISABLED

must_change_password

created_at
updated_at
created_by

last_login_at
last_login_ip

password_changed_at
failed_login_count
locked_until
```

Username requirements:

- unique;
- normalized;
- deterministic case handling.

Email may be optional because this is an internal environment that may not use email.

Never store plaintext passwords.

---

## 7. Password Security

Use a modern password hashing scheme.

Prefer, if compatible with the current dependency set:

```text
Argon2id
```

or:

```text
bcrypt
```

If ClearML already uses bcrypt and reusing it is simpler and safe, use bcrypt.

Requirements:

```text
password never stored plaintext
password never logged
password hash never returned by API
password never sent to frontend after creation
```

Provide configurable password policy:

```text
minimum length
maximum length
require uppercase: configurable
require lowercase: configurable
require number: configurable
require special character: configurable
password history: optional
```

Recommended MVP default:

```text
minimum length = 12
```

Do not hardcode password policy only in the frontend.

The backend must enforce it.

---

## 8. Bootstrap Administrator

The system needs a safe way to create the first administrator in an air-gapped environment.

Support an environment/configuration mechanism such as:

```text
CLEARML_IAM_BOOTSTRAP_ADMIN_USERNAME
CLEARML_IAM_BOOTSTRAP_ADMIN_PASSWORD
```

or a bootstrap CLI.

Example:

```bash
clearml-server iam create-admin \
    --username admin
```

Requirements:

- bootstrap only works if no administrator exists;
- never overwrite an existing administrator;
- never log passwords;
- allow the bootstrap mechanism to be disabled afterward;
- support secrets from environment variables or secret files.

Never commit a default password into the repository.

---

## 9. User API

Design the API according to existing ClearML Server conventions.

The conceptual URL syntax below is not mandatory if ClearML uses service/action naming.

Required functional APIs:

```text
IAM Users

list users
get user
create user
update user
disable user
enable user
reset password
delete/deactivate user
change own password

IAM Groups

list groups
get group
create group
update group
delete group
add group member
remove group member

Current user

get current user information

Audit

list IAM audit events
```

Conceptual endpoints:

```text
GET    /iam/users
POST   /iam/users
GET    /iam/users/{id}
PATCH  /iam/users/{id}

POST   /iam/users/{id}/disable
POST   /iam/users/{id}/enable
POST   /iam/users/{id}/reset-password

POST   /iam/change-password

GET    /iam/groups
POST   /iam/groups
PATCH  /iam/groups/{id}
DELETE /iam/groups/{id}

POST   /iam/groups/{id}/members
DELETE /iam/groups/{id}/members/{user_id}

GET    /iam/me

GET    /iam/audit
```

Adapt actual names and conventions after inspecting the ClearML codebase.

---

## 10. IAM Authorization

MVP roles:

```text
ADMIN
USER
```

### ADMIN

May:

```text
create user
edit user
disable user
enable user
reset password
create/delete group
manage group members
view IAM audit log
```

### USER

May:

```text
view own profile
change own password
use normal ClearML functions
```

May not:

```text
list all users unless required
create user
modify another user
change roles
manage groups
view sensitive audit data
```

Authorization MUST be enforced by the backend.

Do not rely on:

```text
hide button in UI
```

for access control.

---

## 11. Do Not Implement Resource-Level ACL in the MVP

Do not attempt to clone all ClearML Enterprise Access Rules in Phase 1.

Do not implement immediately:

```text
Project A visible only to group A
Model X read-only for group B
Dataset ACL
Queue ACL
Task ACL
```

unless the existing codebase shows this can be added in a very small and safe way.

MVP assumption:

```text
Authenticated USER
    |
    +--> uses shared ClearML workspace

ADMIN
    |
    +--> can additionally manage IAM
```

Design the schema/API so resource ACLs can be added later.

Possible future permission model:

```text
Subject
├── user
└── group

Resource
├── project
├── task
├── dataset
├── model
└── queue

Permission
├── READ
├── WRITE
└── ADMIN
```

Do not implement full resource ACL in Phase 1.

---

## 12. Group Model

Schema:

```text
Group
----------------------------
id
name
description

created_at
updated_at
created_by
```

Membership:

```text
GroupMember
----------------------------
group_id
user_id
created_at
created_by
```

Requirements:

- group name must be unique;
- a user may belong to multiple groups;
- deleting a group must not delete users;
- deleting/disabling a user must handle memberships safely.

Reserved groups may include:

```text
admins
users
```

If reserved groups are introduced, document their semantics clearly.

---

## 13. Authentication Behavior

Support:

```text
username + password login
```

Login must check:

```text
user exists
user status == ACTIVE
account not locked
password valid
```

On successful login:

```text
update last_login_at
reset failed_login_count
```

On failure:

```text
increment failed_login_count
```

Add configurable brute-force protection:

```text
after N failures
lock account for X minutes
```

Recommended defaults:

```text
5 failures
15 minute lock
```

Do not leak account existence.

Return:

```text
invalid username or password
```

instead of:

```text
user does not exist
```

---

## 14. Backward Compatibility with fixed_users

Do not break existing ClearML deployments.

Provide migration/backward compatibility.

Preferred behavior:

```text
iam.database_users.enabled = true
```

If false:

```text
existing fixed_users behavior
```

If true:

```text
database-backed IAM
```

Optionally provide a migration utility:

```bash
clearml-server iam import-fixed-users
```

Import:

```text
username
name
password hash if compatible
```

If hashes cannot be migrated safely:

```text
create user
mark must_change_password = true
```

Do not lose existing user configuration.

---

## 15. Service Accounts

Not required for MVP, but the architecture must not block future support.

If simple enough, add:

```text
SERVICE_ACCOUNT
```

Service accounts must not log into the Web UI.

They should use API credentials only.

If this complicates ClearML authentication/token semantics significantly, defer it to Phase 2.

---

## 16. Audit Log

All important IAM actions must be audited.

Events:

```text
USER_CREATED
USER_UPDATED
USER_DISABLED
USER_ENABLED
USER_DELETED

PASSWORD_CHANGED
PASSWORD_RESET

ROLE_CHANGED

GROUP_CREATED
GROUP_UPDATED
GROUP_DELETED

GROUP_MEMBER_ADDED
GROUP_MEMBER_REMOVED

LOGIN_SUCCESS
LOGIN_FAILURE
ACCOUNT_LOCKED
```

Audit record:

```text
id
timestamp

actor_user_id
actor_username

action

target_type
target_id

metadata

source_ip
user_agent
```

Never store:

```text
plaintext password
password hash
JWT
secret
API key
```

Audit logs must be append-only from the Web UI perspective.

Do not provide a delete button in the Web UI.

---

## 17. Web Application

Modify `clearml-web`.

Add:

```text
Settings
   |
   +-- User Management
          |
          +-- Users
          +-- Groups
          +-- Audit Log
```

Only ADMIN users should see this menu.

The backend must still enforce authorization.

---

## 18. Users Page

Expected UI:

```text
Users

Search: [________________]

[ + Add User ]

+----------------------------------------------------------+
| Username | Name | Role  | Status   | Last Login | Action |
+----------------------------------------------------------+
| admin    | Admin| Admin | Active   | ...        | ...    |
| user01   | A    | User  | Active   | ...        | ...    |
| user02   | B    | User  | Disabled | ...        | ...    |
+----------------------------------------------------------+
```

Features:

```text
search
pagination
filter by role
filter by status
sort
create
edit
disable
enable
reset password
```

Destructive actions must use confirmation dialogs.

Example:

```text
Disable user "user01"?

The user will no longer be able to log in.

[Cancel] [Disable]
```

---

## 19. Create User Dialog

Fields:

```text
Username *
Display Name
Email

Role
  User
  Admin

Temporary Password *
Confirm Password *

Force password change on next login
```

Validation:

- username uniqueness;
- password policy;
- password confirmation;
- required fields;
- clear display of API validation errors.

---

## 20. Edit User Dialog

Allow editing:

```text
display name
email
role
status
```

Never display password/hash.

Prevent an admin from disabling itself if it is the last administrator.

Prevent deletion or downgrade of the last administrator.

These invariants must be enforced in the backend.

---

## 21. Reset Password Flow

Administrator selects:

```text
Reset Password
```

The administrator may enter a temporary password, or the backend may generate one.

Do not assume email is available in this air-gapped environment.

If the backend generates a password:

```text
show exactly once
```

Never persist the plaintext password.

Set:

```text
must_change_password = true
```

---

## 22. Change Password UI

Add a function for the current user:

```text
Account / Profile
    |
    +-- Change Password
```

Fields:

```text
Current password
New password
Confirm new password
```

The backend must verify the current password.

Administrator password reset is a separate flow.

---

## 23. Groups Page

UI:

```text
Groups

[ + Add Group ]

+------------------------------------------------+
| Group       | Description      | Members | ... |
+------------------------------------------------+
| cv-team     | CV Engineers     | 12      | ... |
| vlm-team    | VLM Engineers    | 7       | ... |
+------------------------------------------------+
```

Group details:

```text
Group: cv-team

Members
--------------------------------
user01
user05
user07

[ Add Member ]
```

Support:

```text
create group
rename/update
add members
remove members
delete
```

---

## 24. Audit Page

UI:

```text
Audit Log

Filters:
[actor]
[action]
[target]
[date range]

+--------------------------------------------------------------+
| Time | Actor | Action | Target | Source IP                   |
+--------------------------------------------------------------+
```

Pagination is mandatory.

Audit logs may become large.

Do not load the entire history at once.

---

## 25. Frontend Architecture

Follow the existing Angular architecture of `clearml-web`.

Reuse:

- shared components;
- table components;
- forms;
- dialogs;
- API services;
- state management;
- routing;
- notifications/toasts;
- error handling;
- localization patterns, if present.

Do not introduce a second UI framework unless necessary.

Do not create a visual style that looks different from ClearML.

The new UI should look native to ClearML.

---

## 26. Air-Gapped Requirement

All features must work while outbound Internet access is blocked.

Do not add runtime dependencies on:

```text
Google Fonts
CDN JS
CDN CSS
Auth0
Google
Microsoft
GitHub
ClearML Cloud
external telemetry
external CAPTCHA
remote APIs
```

Build-time dependencies may be mirrored into internal package repositories.

Runtime must remain fully local.

If the existing ClearML Web app references external static assets, document them.

Do not automatically download avatars or external resources.

---

## 27. Configuration

Design configuration that matches ClearML conventions.

Conceptual example:

```text
iam {
    enabled: true

    local_users {
        enabled: true
    }

    password_policy {
        min_length: 12
    }

    lockout {
        max_attempts: 5
        duration_minutes: 15
    }

    audit {
        enabled: true
    }
}
```

Actual naming must follow the existing ClearML Server configuration style.

Do not hardcode deployment-specific values.

---

## 28. Security Requirements

This is security-sensitive code.

### Authentication

Verify:

```text
secure password hashing
timing-safe password comparison
generic login error
account disable enforced immediately
token expiration behavior
```

### Authorization

Every admin API must:

```text
require authenticated ADMIN
```

Never trust a role submitted by the frontend.

Role information must come from a trusted backend identity/token/database.

### Input Validation

Validate:

```text
username
email
display name
group name
pagination
sort field
filter
```

Prevent:

```text
NoSQL injection
query operator injection
mass assignment
IDOR
```

Do not allow the client to submit arbitrary MongoDB query expressions.

### Logging

Never log:

```text
password
password hash
JWT
refresh token
secret
API credentials
```

### CSRF / XSS

Respect the current ClearML authentication architecture.

Escape all user-controlled text in the Web UI.

### Last Administrator Protection

Never allow:

```text
disable last admin
delete last admin
downgrade last admin
```

---

## 29. Token Invalidation

Inspect the existing ClearML token implementation.

When a user is:

```text
disabled
deleted
role changed
password reset
```

determine whether existing JWTs remain valid.

If tokens are stateless and there is no existing revocation mechanism, implement a strategy such as:

```text
user.auth_version
```

Include in token:

```text
auth_version
```

Validate on each request:

```text
token.auth_version == user.auth_version
```

Increment `auth_version` when:

```text
password reset
password changed
user disabled
critical role change
```

If ClearML already has a token revocation mechanism, reuse it instead.

Document the chosen approach.

---

## 30. Database Migration

Support safe database upgrades.

Do not assume a blank database.

Migration must be:

```text
idempotent
backward-safe
repeatable where appropriate
```

Consider indexes:

```text
users.username UNIQUE
users.email optional index
users.status
groups.name UNIQUE
group_members user/group compound index
audit.timestamp
audit.actor
audit.action
```

Do not introduce a migration that could block a production database for a long time without documenting the impact.

---

## 31. Tests

Backend tests are mandatory.

### Authentication Tests

```text
valid login
invalid password
unknown user
disabled user
locked user
password reset
change password
```

### Authorization Tests

```text
admin can create user
normal user cannot create user
normal user cannot disable another user
normal user cannot assign admin role
```

### Safety Tests

```text
cannot disable last admin
cannot delete last admin
cannot downgrade last admin
```

### Group Tests

```text
create
update
delete
add member
remove member
duplicate membership
```

### Audit Tests

Verify that important actions create audit records.

### Frontend Tests

At minimum cover:

```text
IAM menu visibility
Users page rendering
Create user form
Disable confirmation
Group management
API error display
```

---

## 32. Integration Test

Create an end-to-end scenario:

```text
1. Start ClearML Server locally.

2. Bootstrap:
   admin / temporary password

3. Login to the Web UI as admin.

4. Open:
   Settings -> User Management.

5. Create:
   user01.

6. Logout.

7. Login as user01.

8. Verify:
   normal ClearML pages work.

9. Verify:
   User Management menu is not visible.

10. Directly call an IAM admin API using the user01 token.

11. Verify:
   permission is denied.

12. Login as admin.

13. Disable user01.

14. Verify:
   user01 can no longer authenticate.

15. Verify existing session/token behavior follows the documented
    invalidation mechanism.

16. Verify audit events exist.
```

---

## 33. Docker Deployment

Update Docker/dev deployment if needed.

Goal:

```bash
docker compose up
```

must be able to run:

```text
ClearML Server
ClearML Web
MongoDB
Elasticsearch
Redis
IAM extension
```

Do not add another database if the existing MongoDB is sufficient.

Document persistent volumes.

Document upgrade and migration steps.

---

## 34. Deliverables

Final output must include:

```text
1. Architecture analysis
2. Implementation
3. Backend APIs
4. MongoDB schema/indexes
5. User Management UI
6. Groups UI
7. Audit UI
8. Password change UI
9. Bootstrap admin mechanism
10. Migration from fixed_users
11. Tests
12. Docker deployment changes
13. Security notes
14. Upgrade documentation
15. Air-gap deployment documentation
```

---

## 35. Documentation

Create:

```text
docs/iam/architecture.md
docs/iam/configuration.md
docs/iam/deployment.md
docs/iam/security.md
docs/iam/migration-fixed-users.md
```

Architecture documentation must include:

```text
ClearML Web
    |
    v
ClearML API
    |
    v
IAM Service
    |
    +--> Users
    +--> Groups
    +--> Audit
    |
    v
MongoDB
```

---

## 36. Coding Standards

Do not perform large unrelated refactors.

Prefer:

```text
small isolated changes
clear interfaces
testable modules
backward compatibility
```

Follow existing coding conventions in both ClearML repositories.

Do not introduce heavy dependencies when the standard library or existing dependencies are sufficient.

Security-sensitive functions must be easy to review.

---

## 37. Do Not Do the Following

Do not:

```text
copy ClearML Enterprise implementation
reverse-engineer proprietary binaries
bypass ClearML licensing
disable Enterprise license checks
fake Enterprise entitlement
patch UI to expose hidden Enterprise APIs
```

The IAM feature must be a new implementation for the internal fork.

Do not change the business logic of:

```text
experiments
models
datasets
pipelines
queues
agents
```

except where required to propagate or resolve current-user identity.

---

## 38. Phase 2 — Design for It, Do Not Fully Implement It Yet

Design the code so that future work can add:

```text
LDAP / FreeIPA
OIDC internal IdP
Service Accounts
Project ACL
Dataset ACL
Model ACL
Task ACL
Queue ACL
API Keys
MFA
Password expiration
Session management
```

Do not let the MVP architecture block these future capabilities.

---

## 39. Optional Authentication Provider Interface

If it is easy to implement cleanly, use an abstraction such as:

```text
AuthenticationProvider

├── LocalDatabaseProvider
└── future:
    ├── LDAPProvider
    └── OIDCProvider
```

MVP only requires:

```text
LocalDatabaseProvider
```

Do not implement LDAP in Phase 1 unless it is straightforward and low-risk.

---

## 40. Definition of Done

The feature is complete when:

```text
✓ ClearML runs entirely inside the LAN.

✓ Admin can create and manage accounts from ClearML Web.

✓ Users are persisted in the database.

✓ Adding a user no longer requires editing apiserver.conf.

✓ Passwords are hashed securely.

✓ Disabled accounts cannot log in.

✓ Normal users cannot call IAM admin APIs.

✓ ADMIN/USER roles are enforced by the backend.

✓ Groups CRUD works.

✓ Audit log records IAM events.

✓ Existing ClearML experiment/model/dataset functionality
  does not regress.

✓ Existing fixed_users deployments have a migration/backward path.

✓ Docker deployment works.

✓ Unit/integration tests pass.

✓ Runtime does not require Internet access.

✓ Security-sensitive behavior is documented.
```

---

## 41. Execution Order

Perform the task in this order:

```text
STEP 1
Inspect repository structure.

STEP 2
Write a concise architecture findings report:
- current auth flow
- token flow
- relevant files/classes
- DB abstraction
- frontend auth flow

STEP 3
Propose a minimal-change design.

STEP 4
Implement backend IAM.

STEP 5
Add migrations/indexes.

STEP 6
Implement frontend.

STEP 7
Implement tests.

STEP 8
Run existing regression tests.

STEP 9
Run IAM integration tests.

STEP 10
Write deployment/security documentation.
```

Do not stop at architecture/design if the repository allows implementation to proceed.

If a minor ambiguity appears, choose the least invasive reasonable approach and document the assumption instead of blocking the task.

If any assumption in this prompt conflicts with the current ClearML source code, the current source code is authoritative for implementation details. Adapt the implementation while preserving the functional and security goals above.

---

## 42. Final Agent Report

At the end of the task, report:

```text
## Architecture discovered

## Files changed

## Database changes

## APIs added

## UI added

## Authentication flow

## Authorization rules

## Token invalidation strategy

## Backward compatibility

## Air-gap considerations

## Security considerations

## Tests executed

## Known limitations

## Recommended Phase 2
```

Explicitly list concrete file paths such as:

```text
clearml-server:
  path/to/file.py
  path/to/file.py

clearml-web:
  path/to/component.ts
  path/to/service.ts
```

and briefly explain the responsibility of each changed file.

The final objective is to turn ClearML OSS into an internal MLOps platform with **database-backed local user management**, **admin UI**, **groups**, and **audit logging**, operating **100% air-gapped**, while keeping ClearML's existing experiment, model, dataset, pipeline, queue, and agent functionality as unchanged as possible.
