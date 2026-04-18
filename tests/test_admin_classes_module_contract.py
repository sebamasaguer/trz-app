from app.routers import admin_classes as router_mod


def test_router_exports_expected_symbols():
    assert hasattr(router_mod, "router")
    assert hasattr(router_mod, "PaymentMethod")
    assert hasattr(router_mod, "GymClass")
    assert hasattr(router_mod, "ClassGroup")
    assert hasattr(router_mod, "ClassEnrollment")


def test_router_has_expected_paths():
    paths = {getattr(route, "path", "") for route in router_mod.router.routes}

    assert "/admin/classes" in paths
    assert "/admin/classes/new" in paths
    assert "/admin/classes/{class_id}/groups/new" in paths
    assert "/admin/classes/enrollments" in paths
    assert "/admin/classes/groups/{group_id}/enroll" in paths
    assert "/admin/classes/enrollments/{enrollment_id}/cancel" in paths
    assert "/admin/classes/groups/{group_id}" in paths


def test_classes_redirect_targets_listing():
    response = router_mod._classes_redirect()
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/classes"


def test_classes_enrollments_redirect_targets_listing():
    response = router_mod._classes_enrollments_redirect()
    assert response.status_code == 302
    assert response.headers["location"] == "/admin/classes/enrollments"