from mongoengine import DateTimeField, Document, StringField

from apiserver.database import Database, strict


class DataStudioConnection(Document):
    """Private integration credentials, separate from all public user models."""

    meta = {
        "db_alias": Database.auth,
        "strict": strict,
        "collection": "datastudio_connections",
        "indexes": [{"fields": ["company", "user"], "unique": True}],
    }

    id = StringField(primary_key=True)
    company = StringField(required=True)
    user = StringField(required=True)
    username = StringField(required=True)
    encrypted_token = StringField(required=True)
    # Bind credentials to the configured upstream to avoid sending an existing
    # token to a different service after an administrator changes its URL.
    api_url = StringField(required=True)
    checked_at = DateTimeField(required=True)
