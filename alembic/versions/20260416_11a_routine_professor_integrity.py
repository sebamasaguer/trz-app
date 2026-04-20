"""routine/professor integrity hardening

Revision ID: 20260416_11a
Revises: 20260416_10b
Create Date: 2026-04-16
"""

from alembic import op
from sqlalchemy import inspect


revision = "20260416_11a"
down_revision = "20260416_10b"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)

    # ------------------------------------------------------------------
    # 1) Desactivar duplicados activos de routine_assignments
    #    Mantener la fila activa más nueva por student_id
    # ------------------------------------------------------------------
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                student_id,
                ROW_NUMBER() OVER (
                    PARTITION BY student_id
                    ORDER BY id DESC
                ) AS rn
            FROM routine_assignments
            WHERE is_active = true
        )
        UPDATE routine_assignments ra
        SET is_active = false
        FROM ranked r
        WHERE ra.id = r.id
          AND r.rn > 1
        """
    )

    # ------------------------------------------------------------------
    # 2) Deduplicar profesor_alumnos
    #    Mantener la fila más vieja por par profesor/alumno
    # ------------------------------------------------------------------
    op.execute(
        """
        DELETE FROM profesor_alumnos pa
        USING profesor_alumnos dup
        WHERE pa.profesor_id = dup.profesor_id
          AND pa.alumno_id = dup.alumno_id
          AND pa.id > dup.id
        """
    )

    # ------------------------------------------------------------------
    # 3) Constraint único del vínculo profesor/alumno
    # ------------------------------------------------------------------
    existing_constraints = [c["name"] for c in inspector.get_unique_constraints("profesor_alumnos")]
    if "uq_profesor_alumnos_profesor_alumno" not in existing_constraints:
        op.create_unique_constraint(
            "uq_profesor_alumnos_profesor_alumno",
            "profesor_alumnos",
            ["profesor_id", "alumno_id"],
        )

    existing_indexes_pa = [idx["name"] for idx in inspector.get_indexes("profesor_alumnos")]
    if "ix_profesor_alumnos_profesor_alumno" not in existing_indexes_pa:
        op.create_index(
            "ix_profesor_alumnos_profesor_alumno",
            "profesor_alumnos",
            ["profesor_id", "alumno_id"],
            unique=False,
        )

    # ------------------------------------------------------------------
    # 4) Índice único parcial: una sola rutina activa por alumno
    # ------------------------------------------------------------------
    existing_indexes_ra = [idx["name"] for idx in inspector.get_indexes("routine_assignments")]
    if "ux_routine_assignments_student_active" not in existing_indexes_ra:
        op.execute(
            """
            CREATE UNIQUE INDEX ux_routine_assignments_student_active
            ON routine_assignments (student_id)
            WHERE is_active = true
            """
        )

    if "ix_routine_assignments_student_active_created_at" not in existing_indexes_ra:
        op.create_index(
            "ix_routine_assignments_student_active_created_at",
            "routine_assignments",
            ["student_id", "is_active", "created_at"],
            unique=False,
        )


def downgrade():
    op.drop_index("ix_routine_assignments_student_active_created_at", table_name="routine_assignments")
    op.execute("DROP INDEX IF EXISTS ux_routine_assignments_student_active")
    op.drop_index("ix_profesor_alumnos_profesor_alumno", table_name="profesor_alumnos")
    op.drop_constraint("uq_profesor_alumnos_profesor_alumno", "profesor_alumnos", type_="unique")
