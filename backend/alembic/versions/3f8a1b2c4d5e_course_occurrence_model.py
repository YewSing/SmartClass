"""course_occurrence_model

Replaces the flat Class/ClassEnrollment/LecturerClass schema with a two-level
hierarchy: Course → ClassOccurrence (with direct lecturer FK and schedule fields)
→ Enrollment.  AttendanceSession now references occurrence_id instead of class_id.

Revision ID: 3f8a1b2c4d5e
Revises: c5af6efb5917
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "3f8a1b2c4d5e"
down_revision = "c5af6efb5917"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop the FK constraint and class_id column from attendance_sessions first
    #    (SQLite-style: drop constraint by recreating; for Postgres use drop_constraint)
    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.drop_index("ix_attendance_sessions_class_id")
        batch_op.drop_column("class_id")

    # 2. Drop dependent junction tables before dropping classes
    op.drop_table("class_enrollments")
    op.drop_table("lecturer_classes")
    op.drop_table("classes")

    # 3. Create courses
    op.create_table(
        "courses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
    )
    op.create_index("ix_courses_code", "courses", ["code"], unique=True)

    # 4. Create class_occurrences
    op.create_table(
        "class_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("course_id", sa.Integer(), sa.ForeignKey("courses.id"), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("day_of_week", sa.String(10), nullable=False),
        sa.Column("start_time", sa.String(10), nullable=False),
        sa.Column("end_time", sa.String(10), nullable=False),
        sa.Column("room", sa.String(255), nullable=True),
        sa.Column("lecturer_id", sa.Integer(), sa.ForeignKey("lecturers.id"), nullable=False),
        sa.Column("label", sa.String(100), nullable=True),
    )
    op.create_index("ix_class_occurrences_course_id", "class_occurrences", ["course_id"])
    op.create_index("ix_class_occurrences_lecturer_id", "class_occurrences", ["lecturer_id"])

    # 5. Create enrollments
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("occurrence_id", sa.Integer(), sa.ForeignKey("class_occurrences.id"), nullable=False),
        sa.UniqueConstraint("student_id", "occurrence_id", name="uq_enrollment_student_occurrence"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_occurrence_id", "enrollments", ["occurrence_id"])

    # 6. Add occurrence_id to attendance_sessions (nullable — seeded fresh after migration)
    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.add_column(sa.Column("occurrence_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_attendance_sessions_occurrence_id", ["occurrence_id"])
        batch_op.create_foreign_key(
            "fk_attendance_sessions_occurrence_id",
            "class_occurrences",
            ["occurrence_id"],
            ["id"],
        )


def downgrade() -> None:
    # Reverse: restore old tables, swap attendance_sessions columns
    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.drop_constraint("fk_attendance_sessions_occurrence_id", type_="foreignkey")
        batch_op.drop_index("ix_attendance_sessions_occurrence_id")
        batch_op.drop_column("occurrence_id")

    op.drop_table("enrollments")
    op.drop_table("class_occurrences")
    op.drop_table("courses")

    op.create_table(
        "classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("semester", sa.String(100), nullable=False),
        sa.Column("venue", sa.String(255), nullable=True),
    )
    op.create_table(
        "class_enrollments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("students.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.UniqueConstraint("student_id", "class_id"),
    )
    op.create_table(
        "lecturer_classes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lecturer_id", sa.Integer(), sa.ForeignKey("lecturers.id"), nullable=False),
        sa.Column("class_id", sa.Integer(), sa.ForeignKey("classes.id"), nullable=False),
        sa.UniqueConstraint("lecturer_id", "class_id"),
    )

    with op.batch_alter_table("attendance_sessions") as batch_op:
        batch_op.add_column(sa.Column("class_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_attendance_sessions_class_id", ["class_id"])
        batch_op.create_foreign_key(
            "fk_attendance_sessions_class_id",
            "classes",
            ["class_id"],
            ["id"],
        )
