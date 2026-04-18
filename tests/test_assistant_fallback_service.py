from app.services.assistant_fallback_service import local_intent_fallback


def test_local_intent_fallback_detects_price_request():
    result = local_intent_fallback("quiero saber precios")
    assert result["intent"] == "price_request"
    assert result["should_handoff_human"] is False


def test_local_intent_fallback_detects_handoff():
    result = local_intent_fallback("quiero hablar con una persona")
    assert result["intent"] == "handoff_requested"
    assert result["should_handoff_human"] is True
    assert result["lead_temperature"] == "hot"


def test_local_intent_fallback_detects_ready_to_close():
    result = local_intent_fallback("quiero inscribirme")
    assert result["intent"] == "ready_to_close"
    assert result["should_handoff_human"] is True


def test_local_intent_fallback_default_path():
    result = local_intent_fallback("hola")
    assert result["intent"] == "general_query"
    assert "reply_text" in result