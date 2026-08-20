from agi_platform.security import Identity, PolicyEngine, TenantContext


def ctx(identity):
    return TenantContext(identity.tenant_id, identity, 'rid')


def test_authenticated_user_without_permission_gets_403_decision():
    ident = Identity('u', 'a', frozenset(), frozenset())
    assert not PolicyEngine().authorize(ident, ctx(ident), 'memory.read').allowed


def test_correct_permission_wrong_tenant_denied():
    ident = Identity('u', 'a', frozenset(), frozenset({'memory.read'}))
    assert not PolicyEngine().authorize(ident, ctx(ident), 'memory.read', {'tenant_id':'b'}).allowed


def test_high_risk_action_without_approval_denied():
    ident = Identity('u', 'a', frozenset(), frozenset({'sandbox.execute'}))
    assert not PolicyEngine().authorize(ident, ctx(ident), 'sandbox.execute', {'tenant_id':'a'}, {}).allowed


def test_admin_cannot_bypass_tenant_boundary():
    ident = Identity('admin', 'a', frozenset({'admin'}), frozenset({'*'}))
    assert not PolicyEngine().authorize(ident, ctx(ident), 'memory.read', {'tenant_id':'b'}).allowed


def test_malformed_authorization_context_denied():
    ident = Identity('u', 'a', frozenset(), frozenset({'not.real'}))
    assert not PolicyEngine().authorize(ident, None, 'not.real').allowed
