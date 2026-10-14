from apiserver.apierrors import errors
from apiserver.bll import datastudio
from apiserver.service_repo import APICall, endpoint


def _user(call, company):
    if not company or not call.identity.user:
        raise errors.unauthorized.NoCredentials()
    return call.identity.user


@endpoint("datastudio.status", validate_schema=True)
def status(call: APICall, company: str, _):
    return datastudio.status(company, _user(call, company))


# Validate this credential-bearing payload explicitly: generic JSON-schema
# errors include the offending value in their response and logs.
@endpoint("datastudio.connect")
def connect(call: APICall, company: str, _):
    user = _user(call, company)
    username, token = datastudio.parse_credentials(call.data)
    return datastudio.connect(company, user, username, token)


@endpoint("datastudio.disconnect", validate_schema=True)
def disconnect(call: APICall, company: str, _):
    return datastudio.disconnect(company, _user(call, company))


@endpoint("datastudio.datasets", validate_schema=True)
def datasets(call: APICall, company: str, _):
    return datastudio.datasets(company, _user(call, company))


@endpoint("datastudio.revisions", validate_schema=True)
def revisions(call: APICall, company: str, _):
    return datastudio.revisions(company, _user(call, company), call.data["namespace"], call.data["dataset"])
