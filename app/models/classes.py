from datetime import datetime, time
from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .enums import ClassStatus, EnrollmentStatus, ServiceKind, Weekday


class GymClass(Base):
    __tablename__ = "gym_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    service_kind: Mapped[ServiceKind] = mapped_column(
        SAEnum(ServiceKind, name="service_kind"),
        default=ServiceKind.FUNCIONAL,
        index=True,
    )
    status: Mapped[ClassStatus] = mapped_column(
        SAEnum(ClassStatus, name="class_status"),
        default=ClassStatus.ACTIVA,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    groups: Mapped[list["ClassGroup"]] = relationship(
        back_populates="gym_class",
        cascade="all, delete-orphan",
    )


class ClassGroup(Base):
    __tablename__ = "class_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("gym_classes.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(120), default="")
    weekday: Mapped[Weekday] = mapped_column(
        SAEnum(Weekday, name="weekday_enum"),
        index=True,
    )
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    capacity: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    gym_class: Mapped["GymClass"] = relationship(back_populates="groups")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])

    enrollments: Mapped[list["ClassEnrollment"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class ClassEnrollment(Base):
    __tablename__ = "class_enrollments"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("class_groups.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus, name="enrollment_status"),
        default=EnrollmentStatus.ACTIVA,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, default="")
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    group: Mapped["ClassGroup"] = relationship(back_populates="enrollments", foreign_keys=[group_id])
    student: Mapped["User"] = relationship(foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])