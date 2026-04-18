from datetime import date

from app.models import FollowupKind, FollowupStatus
from app.services.followup_rules_service import run_followup_rules_for_all


def test_run_followup_rules_for_all_processes_rows_once(
    db_session,
    admin_user,
    basic_followup,
    monkeypatch,
):
    sent_ids = []

    basic_followup.kind = FollowupKind.GENERAL
    basic_followup.status = FollowupStatus.PENDIENTE
    basic_followup.automation_enabled = True
    basic_followup.next_contact_date = date.today()
    basic_followup.outbound_in_progress = False
    db_session.commit()

    def fake_send_via_n8n(db, row, me, channel):
        sent_ids.append(row.id)
        return {
            "ok": True,
            "duplicate_prevented": False,
            "external_ref": f"ref-{row.id}",
        }

    monkeypatch.setattr(
        "app.services.followup_rules_service.send_via_n8n",
        fake_send_via_n8n,
    )

    summary = run_followup_rules_for_all(db_session, me=admin_user)

    assert summary["ok"] is True
    assert summary["evaluated"] >= 1
    assert sent_ids.count(basic_followup.id) == 1


def test_run_followup_rules_for_all_skips_outbound_in_progress(
    db_session,
    admin_user,
    basic_followup,
    monkeypatch,
):
    basic_followup.kind = FollowupKind.GENERAL
    basic_followup.status = FollowupStatus.PENDIENTE
    basic_followup.automation_enabled = True
    basic_followup.next_contact_date = date.today()
    basic_followup.outbound_in_progress = True
    db_session.commit()

    def fake_send_via_n8n(db, row, me, channel):
        raise AssertionError("No debería enviar si outbound_in_progress=True")

    monkeypatch.setattr(
        "app.services.followup_rules_service.send_via_n8n",
        fake_send_via_n8n,
    )

    summary = run_followup_rules_for_all(db_session, me=admin_user)

    assert summary["ok"] is True
    assert summary["evaluated"] >= 1
    assert summary["skipped"] >= 1