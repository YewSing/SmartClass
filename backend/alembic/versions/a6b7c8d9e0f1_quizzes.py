"""Module 6 quiz tables.
Revision ID: a6b7c8d9e0f1
Revises: f5a6b7c8d9e0
"""
from alembic import op
import sqlalchemy as sa
revision='a6b7c8d9e0f1'; down_revision='f5a6b7c8d9e0'; branch_labels=None; depends_on=None
def upgrade():
    op.create_table('m6_quizzes',sa.Column('id',sa.Integer,primary_key=True),sa.Column('course_id',sa.Integer,sa.ForeignKey('courses.id'),nullable=False),sa.Column('lecturer_id',sa.Integer,sa.ForeignKey('lecturers.id'),nullable=False),sa.Column('title',sa.String(255),nullable=False),sa.Column('quiz_type',sa.String(12),nullable=False),sa.Column('status',sa.String(16),server_default='draft',nullable=False),sa.Column('timer_mode',sa.String(16),server_default='whole',nullable=False),sa.Column('timer_seconds',sa.Integer),sa.Column('opens_at',sa.DateTime),sa.Column('closes_at',sa.DateTime),sa.Column('shuffle',sa.Boolean,server_default=sa.false(),nullable=False),sa.Column('release_marks',sa.Boolean,server_default=sa.false(),nullable=False),sa.Column('release_answers',sa.Boolean,server_default=sa.false(),nullable=False),sa.Column('speed_bonus',sa.Boolean,server_default=sa.true(),nullable=False),sa.Column('current_question',sa.Integer),sa.Column('questions',sa.JSON,nullable=False),sa.Column('created_at',sa.DateTime,server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime,server_default=sa.func.now(),nullable=False))
    op.create_index('ix_m6_quizzes_course_id','m6_quizzes',['course_id']);op.create_index('ix_m6_quizzes_lecturer_id','m6_quizzes',['lecturer_id'])
    op.create_table('m6_attempts',sa.Column('id',sa.Integer,primary_key=True),sa.Column('quiz_id',sa.Integer,sa.ForeignKey('m6_quizzes.id',ondelete='CASCADE'),nullable=False),sa.Column('student_id',sa.Integer,sa.ForeignKey('students.id'),nullable=False),sa.Column('status',sa.String(16),server_default='in_progress',nullable=False),sa.Column('answers',sa.JSON,nullable=False),sa.Column('score',sa.Float),sa.Column('started_at',sa.DateTime,server_default=sa.func.now(),nullable=False),sa.Column('deadline_at',sa.DateTime),sa.Column('submitted_at',sa.DateTime),sa.UniqueConstraint('quiz_id','student_id',name='uq_m6_attempt_quiz_student'))
    op.create_index('ix_m6_attempts_quiz_id','m6_attempts',['quiz_id']);op.create_index('ix_m6_attempts_student_id','m6_attempts',['student_id'])
def downgrade(): op.drop_table('m6_attempts');op.drop_table('m6_quizzes')
