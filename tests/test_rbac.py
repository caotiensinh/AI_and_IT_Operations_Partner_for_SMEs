import unittest
from uuid import uuid4

from sme_partner.rbac import (
    Action, Assignment, PermissionDenied, Resource, Role, ScopeType, require_permission,
)
from sme_partner.tenant_context import AuthorizedTenantContext, TenantAccessDenied


class ScopedRBAC(unittest.TestCase):
    def setUp(self):
        self.tenant,self.other,self.user,self.stranger=[uuid4() for _ in range(4)]
        self.site1,self.site2,self.dept1,self.dept2=[uuid4() for _ in range(4)]
        self.context=AuthorizedTenantContext(self.user,self.tenant)
        self.resource=Resource(self.tenant,self.site1,self.dept1)
    def grant(self,role,scope_type=ScopeType.TENANT,scope_id=None,identity=None,tenant=None):
        return Assignment(tenant or self.tenant,identity or self.user,role,scope_type,scope_id)
    def allows(self,grants,action=Action.READ,resource=None):
        require_permission(self.context,tuple(grants),action,resource or self.resource)
    def test_owner_tenant_grant(self):
        self.allows([self.grant(Role.OWNER)],Action.MANAGE_USERS)
    def test_admin_tenant_settings(self):
        self.allows([self.grant(Role.ADMIN)],Action.CONFIGURE)
    def test_viewer_cannot_write(self):
        with self.assertRaises(PermissionDenied):self.allows([self.grant(Role.VIEWER)],Action.UPDATE)
    def test_operator_can_acknowledge_but_not_approve(self):
        grant=self.grant(Role.OPERATOR)
        self.allows([grant],Action.ACKNOWLEDGE)
        with self.assertRaises(PermissionDenied):self.allows([grant],Action.APPROVE)
    def test_manager_site_scoped(self):
        grant=self.grant(Role.MANAGER,ScopeType.SITE,self.site1)
        self.allows([grant],Action.APPROVE)
        with self.assertRaises(PermissionDenied):
            self.allows([grant],Action.APPROVE,Resource(self.tenant,self.site2,self.dept2))
    def test_department_scope_and_ancestor(self):
        grant=self.grant(Role.MANAGER,ScopeType.DEPARTMENT,self.dept1)
        self.allows([grant])
        nested=Resource(self.tenant,self.site1,self.dept2,frozenset({self.dept1}))
        self.allows([grant],resource=nested)
        with self.assertRaises(PermissionDenied):
            self.allows([grant],resource=Resource(self.tenant,self.site1,self.dept2))
    def test_cross_tenant_resource_denied_even_owner(self):
        with self.assertRaises(TenantAccessDenied):
            self.allows([self.grant(Role.OWNER)],resource=Resource(self.other,self.site1,self.dept1))
    def test_cross_tenant_grant_ignored(self):
        with self.assertRaises(PermissionDenied):self.allows([self.grant(Role.OWNER,tenant=self.other)])
    def test_foreign_identity_grant_ignored(self):
        with self.assertRaises(PermissionDenied):self.allows([self.grant(Role.OWNER,identity=self.stranger)])
    def test_empty_or_invalid_scope_denied(self):
        with self.assertRaises(PermissionDenied):self.allows([])
        with self.assertRaises(PermissionDenied):
            self.allows([self.grant(Role.MANAGER,ScopeType.DEPARTMENT,None)])
    def test_invalid_role_action_denied(self):
        with self.assertRaises(PermissionDenied):
            self.allows([self.grant("owner")],Action.READ)
        with self.assertRaises(PermissionDenied):
            require_permission(self.context,(self.grant(Role.OWNER),),"resource.read",self.resource)
