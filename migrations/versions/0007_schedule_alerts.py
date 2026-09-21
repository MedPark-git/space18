"""GMP and GTP work schedule alerts"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import date

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    task=op.create_table(
        "schedule_task",
        sa.Column("id",sa.Uuid(),primary_key=True),
        sa.Column("standard",sa.String(10),nullable=False),
        sa.Column("section",sa.String(50),nullable=False),
        sa.Column("title",sa.String(250),nullable=False),
        sa.Column("due_date",sa.Date(),nullable=False),
        sa.Column("date_precision",sa.String(20),nullable=False,server_default="day"),
        sa.Column("reminder_days",sa.Integer(),nullable=False,server_default="60"),
        sa.Column("owner",sa.String(100),nullable=False,server_default=""),
        sa.Column("status",sa.String(30),nullable=False,server_default="scheduled"),
        sa.Column("memo",sa.Text(),nullable=False,server_default=""),
        sa.Column("completed_at",sa.DateTime(timezone=True)),
        sa.Column("created_by",sa.Uuid(),sa.ForeignKey("user.id")),
        sa.Column("updated_by",sa.Uuid(),sa.ForeignKey("user.id")),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
    )
    op.create_index("ix_schedule_task_standard_due","schedule_task",["standard","due_date"])
    op.create_index("ix_schedule_task_status","schedule_task",["status"])
    op.bulk_insert(task,[{
        "id":uuid.UUID("5ced0000-0007-4000-8000-000000000001"),
        "standard":"GMP","section":"validation","title":"1009호 클린룸 밸리데이션",
        "due_date":date(2027,1,31),"date_precision":"month","reminder_days":60,
        "owner":"품질부서","status":"scheduled",
        "memo":"2027년 1월 예정. 정확한 수행일 확정 시 날짜를 수정하세요."
    }])

def downgrade():
    op.drop_table("schedule_task")
