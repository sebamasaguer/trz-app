from datetime import datetime, UTC

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    User,
    Prospect,
    ProspectStatus,
    StudentFollowup,
    FollowupKind,
    FollowupStatus,
    FollowupPriority,
    FollowupChannel,
    FollowupAction,
    FollowupActionType,
    ContactConversation,
    ConversationStatus,
    CommercialStage,
)


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def find_open_followup_for_student(db: Session, student_id: int | None) -> StudentFollowup | None:
    if not student_id:
        return None

    return db.scalars(
        select(StudentFollowup)
        .where(
            StudentFollowup.student_id == student_id,
            StudentFollowup.status.in_(
                [
                    FollowupStatus.PENDIENTE,
                    FollowupStatus.CONTACTADO,
                    FollowupStatus.RESPONDIO,
                ]
            ),
        )
        .order_by(StudentFollowup.id.desc())
    ).first()


def ensure_followup_for_reactivation(
    db: Session,
    student: User,
    summary: str = "",
    *,
    auto_commit: bool = True,
) -> StudentFollowup:
    row = find_open_followup_for_student(db, student.id)
    if row:
        return row

    row = StudentFollowup(
        student_id=student.id,
        created_by_id=None,
        kind=FollowupKind.INACTIVIDAD,
        status=FollowupStatus.RESPONDIO,
        priority=FollowupPriority.MEDIA,
        channel=FollowupChannel.WHATSAPP,
        title="Conversación automática desde WhatsApp",
        notes="Generado automáticamente por asistente virtual",
        result_summary=(summary or "").strip(),
        contacted_at=_utcnow_naive(),
        last_action_at=_utcnow_naive(),
        last_action_type=FollowupActionType.NOTA.value,
    )
    db.add(row)

    if auto_commit:
        db.commit()
        db.refresh(row)
    else:
        db.flush()

    return row


def create_handoff_action(
    db: Session,
    conversation: ContactConversation,
    reason: str,
    *,
    auto_commit: bool = True,
) -> None:
    if conversation.followup_id:
        action = FollowupAction(
            followup_id=conversation.followup_id,
            created_by_id=None,
            action_type=FollowupActionType.NOTA,
            channel=FollowupChannel.WHATSAPP,
            summary=f"Derivado a humano: {reason}",
            payload_text="",
            external_ref="",
            delivery_status="DERIVADO",
            response_payload="",
        )
        db.add(action)

        followup = db.get(StudentFollowup, conversation.followup_id)
        if followup:
            followup.priority = FollowupPriority.ALTA
            followup.result_summary = reason
            followup.last_action_at = _utcnow_naive()
            followup.last_action_type = FollowupActionType.NOTA.value

    if conversation.prospect_id:
        prospect = db.get(Prospect, conversation.prospect_id)
        if prospect:
            prospect.status = ProspectStatus.DERIVADO
            prospect.interest_summary = reason

    conversation.status = ConversationStatus.DERIVADA_A_HUMANO
    conversation.handoff_reason = reason

    if auto_commit:
        db.commit()


def infer_commercial_stage(
    intent: str,
    lead_temperature: str,
    should_handoff_human: bool,
    current_stage: str | None = None,
) -> CommercialStage:
    intent = (intent or "").strip()
    lead_temperature = (lead_temperature or "").strip().lower()

    if intent in ["handoff_requested", "ready_to_close"] or should_handoff_human:
        return CommercialStage.DERIVADO

    if intent in ["price_request", "schedule_preference_defined", "contextual_followup"]:
        return CommercialStage.CALIFICADO

    if intent in ["interes_alto", "general_query"]:
        return CommercialStage.INTERESADO

    if lead_temperature == "hot":
        return CommercialStage.NEGOCIANDO

    if current_stage:
        try:
            return CommercialStage(current_stage)
        except Exception:
            pass

    return CommercialStage.NUEVO