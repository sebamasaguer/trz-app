from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.models import ConversationStatus, CommercialStage, FollowupStatus, FollowupPriority
from app.services import assistant_admin_service as svc


class DummyDB:
    def __init__(self):
        self._objects = {}
        self.added = []
        self.commits = 0

    def get(self, model, obj_id):
        return self._objects.get((model, obj_id))

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1


def test_get_conversation_or_404_returns_row():
    db = DummyDB()
    row = SimpleNamespace(id=10)
    db._objects[(svc.ContactConversation, 10)] = row

    result = svc.get_conversation_or_404(db, 10)

    assert result is row


def test_get_conversation_or_404_raises():
    db = DummyDB()

    with pytest.raises(HTTPException) as exc:
        svc.get_conversation_or_404(db, 999)

    assert exc.value.status_code == 404
    assert exc.value.detail == "Conversación no encontrada"


def test_pause_conversation_marks_paused():
    db = DummyDB()
    me = SimpleNamespace(id=5)
    row = SimpleNamespace(
        id=20,
        followup_id=None,
        prospect_id=None,
        assistant_paused=False,
        assistant_paused_at=None,
        assistant_paused_by_user_id=None,
        status=ConversationStatus.EN_AUTOMATICO,
        updated_at=None,
    )

    svc.pause_conversation(db, row, me)

    assert row.assistant_paused is True
    assert row.assistant_paused_by_user_id == 5
    assert row.status == ConversationStatus.DERIVADA_A_HUMANO
    assert row.updated_at is not None
    assert db.commits == 1


def test_resume_conversation_marks_resumed():
    db = DummyDB()
    row = SimpleNamespace(
        id=21,
        followup_id=None,
        prospect_id=None,
        assistant_paused=True,
        assistant_paused_at=object(),
        assistant_paused_by_user_id=7,
        status=ConversationStatus.DERIVADA_A_HUMANO,
        updated_at=None,
    )

    svc.resume_conversation(db, row)

    assert row.assistant_paused is False
    assert row.assistant_paused_at is None
    assert row.assistant_paused_by_user_id is None
    assert row.status == ConversationStatus.EN_AUTOMATICO
    assert row.updated_at is not None
    assert db.commits == 1


def test_mark_conversation_reactivated_updates_followup_and_adds_action():
    db = DummyDB()
    me = SimpleNamespace(id=3)

    followup = SimpleNamespace(
        id=55,
        status=FollowupStatus.CONTACTADO,
        priority=FollowupPriority.MEDIA,
        last_action_at=None,
        last_action_type=None,
    )
    row = SimpleNamespace(
        id=30,
        followup_id=55,
        updated_at=None,
    )
    db._objects[(svc.StudentFollowup, 55)] = followup

    svc.mark_conversation_reactivated(db=db, row=row, me=me)

    assert followup.status == FollowupStatus.REACTIVADO
    assert followup.priority == FollowupPriority.ALTA
    assert followup.last_action_at is not None
    assert followup.last_action_type == svc.FollowupActionType.NOTA.value
    assert row.updated_at is not None
    assert len(db.added) == 1
    assert db.commits == 1


def test_mark_conversation_handoff_updates_followup_and_prospect():
    db = DummyDB()
    me = SimpleNamespace(id=8)

    followup = SimpleNamespace(
        id=60,
        priority=FollowupPriority.MEDIA,
        last_action_at=None,
        last_action_type=None,
    )
    prospect = SimpleNamespace(
        id=70,
        status=svc.ProspectStatus.NUEVO,
    )
    row = SimpleNamespace(
        id=31,
        followup_id=60,
        prospect_id=70,
        status=ConversationStatus.EN_AUTOMATICO,
        assistant_paused=False,
        assistant_paused_at=None,
        assistant_paused_by_user_id=None,
        handoff_reason="",
        updated_at=None,
    )

    db._objects[(svc.StudentFollowup, 60)] = followup
    db._objects[(svc.Prospect, 70)] = prospect

    svc.mark_conversation_handoff(db=db, row=row, me=me)

    assert row.status == ConversationStatus.DERIVADA_A_HUMANO
    assert row.assistant_paused is True
    assert row.assistant_paused_by_user_id == 8
    assert row.handoff_reason == "Derivación manual desde panel"
    assert followup.priority == FollowupPriority.ALTA
    assert followup.last_action_at is not None
    assert followup.last_action_type == svc.FollowupActionType.NOTA.value
    assert prospect.status == svc.ProspectStatus.DERIVADO
    assert len(db.added) == 1
    assert db.commits == 1


def test_change_conversation_stage_updates_stage():
    db = DummyDB()
    me = SimpleNamespace(id=9)

    row = SimpleNamespace(
        id=40,
        commercial_stage=None,
        commercial_stage_updated_at=None,
        commercial_stage_note="",
        assistant_paused=False,
        assistant_paused_at=None,
        assistant_paused_by_user_id=None,
        status=ConversationStatus.EN_AUTOMATICO,
        updated_at=None,
    )

    svc.change_conversation_stage(
        db=db,
        row=row,
        me=me,
        stage=CommercialStage.CALIFICADO.value,
        note="Etapa actualizada",
    )

    assert row.commercial_stage == CommercialStage.CALIFICADO
    assert row.commercial_stage_updated_at is not None
    assert row.commercial_stage_note == "Etapa actualizada"
    assert row.updated_at is not None
    assert db.commits == 1


def test_change_conversation_stage_to_derivado_pauses_assistant():
    db = DummyDB()
    me = SimpleNamespace(id=11)

    row = SimpleNamespace(
        id=41,
        commercial_stage=None,
        commercial_stage_updated_at=None,
        commercial_stage_note="",
        assistant_paused=False,
        assistant_paused_at=None,
        assistant_paused_by_user_id=None,
        status=ConversationStatus.EN_AUTOMATICO,
        updated_at=None,
    )

    svc.change_conversation_stage(
        db=db,
        row=row,
        me=me,
        stage=CommercialStage.DERIVADO.value,
        note="Pasa a derivado",
    )

    assert row.commercial_stage == CommercialStage.DERIVADO
    assert row.assistant_paused is True
    assert row.assistant_paused_by_user_id == 11
    assert row.status == ConversationStatus.DERIVADA_A_HUMANO
    assert db.commits == 1


def test_change_conversation_stage_invalid_raises():
    db = DummyDB()
    me = SimpleNamespace(id=15)
    row = SimpleNamespace(id=42)

    with pytest.raises(HTTPException) as exc:
        svc.change_conversation_stage(
            db=db,
            row=row,
            me=me,
            stage="ETAPA_INVENTADA",
            note="",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail == "Etapa no válida"