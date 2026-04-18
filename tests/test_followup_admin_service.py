from app.models import (
    FollowupAction,
    FollowupActionType,
    FollowupKind,
    FollowupPriority,
    FollowupStatus,
)
from app.services.followup_admin_service import (
    create_followup,
    update_followup,
    mark_reminder_sent_service,
)


def test_create_followup_creates_row_and_action(db_session, admin_user, student_user):
    row = create_followup(
        db_session,
        student_id=student_user.id,
        kind="GENERAL",
        status="PENDIENTE",
        channel="WHATSAPP",
        title="Nuevo seguimiento",
        notes="Mensaje de prueba",
        next_contact_date="",
        me=admin_user,
    )

    assert row is not None
    assert row.student_id == student_user.id
    assert row.kind == FollowupKind.GENERAL
    assert row.status == FollowupStatus.PENDIENTE
    assert row.title == "Nuevo seguimiento"

    action = db_session.query(FollowupAction).filter(FollowupAction.followup_id == row.id).first()
    assert action is not None
    assert action.action_type == FollowupActionType.NOTA
    assert action.summary == "Seguimiento creado"


def test_update_followup_changes_status_and_creates_action(db_session, admin_user, basic_followup):
    ok = update_followup(
        db_session,
        followup_id=basic_followup.id,
        kind="GENERAL",
        status="CONTACTADO",
        priority="ALTA",
        channel="WHATSAPP",
        title="Título editado",
        notes="Notas editadas",
        next_contact_date="",
        result_summary="Se contactó",
        automation_enabled="1",
        me=admin_user,
    )

    assert ok is True

    db_session.refresh(basic_followup)
    assert basic_followup.status == FollowupStatus.CONTACTADO
    assert basic_followup.priority == FollowupPriority.ALTA
    assert basic_followup.title == "Título editado"
    assert basic_followup.contacted_at is not None

    actions = (
        db_session.query(FollowupAction)
        .filter(FollowupAction.followup_id == basic_followup.id)
        .all()
    )
    assert any(a.action_type == FollowupActionType.CAMBIO_ESTADO for a in actions)


def test_mark_reminder_sent_sets_timestamp_and_action(db_session, admin_user, basic_followup):
    ok = mark_reminder_sent_service(
        db_session,
        followup_id=basic_followup.id,
        me=admin_user,
    )

    assert ok is True
    db_session.refresh(basic_followup)
    assert basic_followup.reminder_sent_at is not None

    actions = (
        db_session.query(FollowupAction)
        .filter(FollowupAction.followup_id == basic_followup.id)
        .all()
    )
    assert any(a.action_type == FollowupActionType.RECORDATORIO for a in actions)