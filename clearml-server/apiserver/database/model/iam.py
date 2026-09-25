from mongoengine import DateTimeField, DictField, Document, StringField

from apiserver.database import Database, strict
from apiserver.database.model import DbModelMixin


class IAMGroup(DbModelMixin, Document):
    meta = {
        "db_alias": Database.auth,
        "strict": strict,
        "collection": "iam_groups",
        "indexes": [
            {"fields": ["company", "name"], "unique": True},
            "company",
        ],
    }

    id = StringField(primary_key=True)
    company = StringField(required=True)
    name = StringField(required=True)
    description = StringField(default="")
    created_at = DateTimeField(required=True)
    updated_at = DateTimeField(required=True)
    created_by = StringField(required=True)


class IAMGroupMember(DbModelMixin, Document):
    meta = {
        "db_alias": Database.auth,
        "strict": strict,
        "collection": "iam_group_members",
        "indexes": [
            {"fields": ["group_id", "user_id"], "unique": True},
            "user_id",
            "group_id",
        ],
    }

    id = StringField(primary_key=True)
    company = StringField(required=True)
    group_id = StringField(required=True)
    user_id = StringField(required=True)
    created_at = DateTimeField(required=True)
    created_by = StringField(required=True)


class IAMAuditEvent(DbModelMixin, Document):
    meta = {
        "db_alias": Database.auth,
        "strict": strict,
        "collection": "iam_audit",
        "indexes": [
            "-timestamp",
            "actor_user_id",
            "action",
            "target_id",
            "company",
        ],
    }

    id = StringField(primary_key=True)
    company = StringField(required=True)
    timestamp = DateTimeField(required=True)
    actor_user_id = StringField()
    actor_username = StringField()
    action = StringField(required=True)
    target_type = StringField(required=True)
    target_id = StringField()
    metadata = DictField(default=dict)
    source_ip = StringField()
    user_agent = StringField()
