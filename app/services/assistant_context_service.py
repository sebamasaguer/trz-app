from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import Membership, MembershipPrice, GymClass, ClassGroup


def get_trz_knowledge(db: Session) -> dict:
    memberships = db.scalars(
        select(Membership).where(Membership.is_active == True).order_by(Membership.name.asc())
    ).all()

    classes = db.scalars(
        select(GymClass).where(GymClass.status == "ACTIVA").order_by(GymClass.name.asc())
    ).all()

    groups = db.scalars(
        select(ClassGroup)
        .where(ClassGroup.is_active == True)
        .order_by(ClassGroup.weekday.asc(), ClassGroup.start_time.asc())
    ).all()

    membership_payload = []
    for membership in memberships:
        prices = db.scalars(
            select(MembershipPrice).where(MembershipPrice.membership_id == membership.id)
        ).all()

        membership_payload.append(
            {
                "name": membership.name,
                "kind": membership.kind.value,
                "funcional_classes": membership.funcional_classes,
                "musculacion_classes": membership.musculacion_classes,
                "funcional_unlimited": membership.funcional_unlimited,
                "musculacion_unlimited": membership.musculacion_unlimited,
                "prices": [
                    {
                        "payment_method": price.payment_method.value,
                        "amount": float(price.amount),
                    }
                    for price in prices
                ],
            }
        )

    class_payload = [
        {"name": gym_class.name, "service_kind": gym_class.service_kind.value}
        for gym_class in classes
    ]

    groups_payload = [
        {
            "class_id": group.class_id,
            "group_name": group.name,
            "weekday": group.weekday.value,
            "start_time": group.start_time.strftime("%H:%M"),
            "end_time": group.end_time.strftime("%H:%M"),
            "capacity": group.capacity,
        }
        for group in groups
    ]

    return {
        "gym_name": "TRZ Funcional",
        "handoff_name": settings.TRZ_HUMAN_HANDOFF_NAME,
        "handoff_phone": settings.TRZ_HUMAN_HANDOFF_PHONE,
        "memberships": membership_payload,
        "classes": class_payload,
        "groups": groups_payload,
        "business_rules": [
            "Responder en tono cálido, comercial y concreto.",
            "No inventar precios, horarios ni promociones.",
            "Si el usuario quiere inscribirse, pagar o hablar con una persona, derivar a humano.",
            "Si el caso es complejo o hay baja confianza, derivar a humano.",
            "Para alumnos inactivos, buscar reactivación y cierre comercial.",
            "Para nuevos prospectos, explicar clases, horarios, membresías y próximos pasos.",
        ],
    }