from app.api.workspace_access import (
    PUBLISH_ROLES,
    WRITE_ROLES,
)
from app.models.membership import MembershipRole


expected = {
    MembershipRole.owner,
    MembershipRole.admin,
    MembershipRole.manager,
}

assert PUBLISH_ROLES == expected

assert MembershipRole.editor in WRITE_ROLES
assert MembershipRole.editor not in PUBLISH_ROLES
assert MembershipRole.viewer not in PUBLISH_ROLES

print("Publish role policy exact set: PASS")
print("Editor publish permission blocked: PASS")
print("Viewer publish permission blocked: PASS")
