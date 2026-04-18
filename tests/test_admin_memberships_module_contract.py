from app.routers import admin_memberships as router_mod


def test_router_exports_expected_symbols():
    assert hasattr(router_mod, "router")
    assert hasattr(router_mod, "PaymentMethod")
    assert hasattr(router_mod, "Membership")
    assert hasattr(router_mod, "MembershipPrice")


def test_router_has_expected_paths():
    paths = {getattr(route, "path", "") for route in router_mod.router.routes}

    assert "/admin/memberships" in paths
    assert "/admin/memberships/new" in paths
    assert "/admin/memberships/{mid}/edit" in paths
    assert "/admin/memberships/assign" in paths
    assert "/admin/memberships/consume" in paths
    assert "/admin/memberships/report" in paths
    assert "/admin/qr" in paths


def test_membership_redirect_points_to_listing():
    response = router_mod._membership_redirect()
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/memberships"