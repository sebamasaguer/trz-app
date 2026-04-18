from app.services.membership_service import (
    normalize_period_input,
    normalize_qr_service,
    qr_page_context,
    report_page_context,
)


def test_normalize_period_input_keeps_valid_period():
    assert normalize_period_input("2026-04") == "2026-04"


def test_normalize_period_input_invalid_returns_current():
    assert normalize_period_input("2026/04", today=None) is not None


def test_normalize_qr_service_accepts_funcional():
    assert normalize_qr_service("funcional") == "FUNCIONAL"


def test_normalize_qr_service_accepts_musculacion():
    assert normalize_qr_service("MUSCULACION") == "MUSCULACION"


def test_normalize_qr_service_invalid_falls_back():
    assert normalize_qr_service("OTRO") == "FUNCIONAL"
    assert normalize_qr_service("") == "FUNCIONAL"


def test_report_page_context_builds_expected_keys():
    ctx = report_page_context(
        request="REQ",
        me="ME",
        period="2026-04",
        rows=[{"x": 1}],
    )
    assert ctx["request"] == "REQ"
    assert ctx["me"] == "ME"
    assert ctx["period"] == "2026-04"
    assert ctx["rows"] == [{"x": 1}]


def test_qr_page_context_builds_expected_keys():
    ctx = qr_page_context(
        request="REQ",
        me="ME",
        service="FUNCIONAL",
        payload="abc123",
    )
    assert ctx["request"] == "REQ"
    assert ctx["me"] == "ME"
    assert ctx["service"] == "FUNCIONAL"
    assert ctx["payload"] == "abc123"