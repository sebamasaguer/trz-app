from datetime import date, datetime
from app.utils.datetime_utils import utcnow_naive

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Enum as SAEnum,
    Index,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base
from .enums import RoutineType


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        Index("ix_exercises_professor_name_id", "professor_id", "name", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(180))
    description: Mapped[str] = mapped_column(String(1000), default="")
    muscle_group: Mapped[str] = mapped_column(String(120), default="")
    equipment: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    professor = relationship("User", lazy="joined")


class Routine(Base):
    __tablename__ = "routines"
    __table_args__ = (
        Index("ix_routines_professor_id_id", "professor_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(180))
    notes: Mapped[str] = mapped_column(String(2000), default="")
    routine_type: Mapped[RoutineType] = mapped_column(
        SAEnum(RoutineType, name="routine_type"),
        default=RoutineType.DIAS,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    professor = relationship("User", lazy="joined")
    items = relationship("RoutineItem", cascade="all, delete-orphan", back_populates="routine")


class RoutineItem(Base):
    __tablename__ = "routine_items"
    __table_args__ = (
        Index(
            "ix_routine_items_routine_day_weekday_order",
            "routine_id",
            "day_label",
            "weekday",
            "order_index",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id", ondelete="RESTRICT"), index=True)

    day_label: Mapped[str] = mapped_column(String(30), default="")
    weekday: Mapped[str] = mapped_column(String(12), default="")

    sets: Mapped[int] = mapped_column(Integer, default=0)
    reps: Mapped[str] = mapped_column(String(50), default="")
    rest_seconds: Mapped[int] = mapped_column(Integer, default=0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str] = mapped_column(String(500), default="")

    routine = relationship("Routine", back_populates="items")
    exercise = relationship("Exercise", lazy="joined")


class RoutineAssignment(Base):
    __tablename__ = "routine_assignments"
    __table_args__ = (
        Index(
            "ux_routine_assignments_student_active",
            "student_id",
            unique=True,
            sqlite_where=text("is_active = 1"),
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "ix_routine_assignments_student_active_created_at",
            "student_id",
            "is_active",
            "created_at",
        ),
        Index(
            "ix_routine_assignments_student_id_id",
            "student_id",
            "id",
        ),
        Index(
            "ix_routine_assignments_routine_active_id",
            "routine_id",
            "is_active",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routines.id", ondelete="CASCADE"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    routine = relationship("Routine", lazy="joined")
    student = relationship("User", foreign_keys=[student_id], lazy="joined")
    professor = relationship("User", foreign_keys=[assigned_by], lazy="joined")


class ProfesorAlumno(Base):
    __tablename__ = "profesor_alumnos"
    __table_args__ = (
        UniqueConstraint("profesor_id", "alumno_id", name="uq_profesor_alumnos_profesor_alumno"),
        Index("ix_profesor_alumnos_profesor_alumno", "profesor_id", "alumno_id"),
        Index("ix_profesor_alumnos_profesor_id_id", "profesor_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profesor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    alumno_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow_naive)

    profesor = relationship("User", foreign_keys=[profesor_id], lazy="joined")
    alumno = relationship("User", foreign_keys=[alumno_id], lazy="joined")