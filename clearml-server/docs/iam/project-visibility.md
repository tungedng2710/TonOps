# Project visibility with local IAM

New projects are **private** by default. The owner and administrators can view and change them. A **public** project can be viewed by any signed-in user in the same company; only the owner or an administrator can change it. The project create form and Project Settings expose the visibility choice.

Existing projects have no `visibility` value. They retain their earlier company-wide readability until an owner or administrator explicitly changes the setting. This avoids hiding projects during an upgrade.

The API applies project access checks to project, task, model, and event calls. The local fileserver asks the API server to authorize each authenticated download, upload, and deletion. Its `fileserver.auth.enabled` setting must remain `true`. Standard task output paths include the task ID; registered model URLs are also checked. Files with custom paths that cannot be linked to a task or model are denied while local IAM is enabled.

Artifacts stored outside the ClearML fileserver use their storage provider's access controls. Public project visibility exposes their URLs to viewers, but does not grant access to private S3, MinIO, or other external buckets. Configure those stores separately for downloads.

Private project metadata may still be referenced by older aggregate endpoints outside the project, task, model, and event services. Review those endpoints before treating this as a complete isolation boundary in a multi-tenant deployment.

## Profile

Signed-in users can update their own display name, given and family names, avatar URL, and bio. The avatar accepts HTTP(S) URLs of up to 2,048 characters, and the bio is limited to 1,000 characters. Local IAM users can also change their password after entering the current password. The API rejects profile updates targeting another user unless the caller is an administrator.
