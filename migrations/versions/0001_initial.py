"""initial schema

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("user",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("login_id", sa.String(80), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("department", sa.String(100), nullable=False),
        sa.Column("position", sa.String(100), nullable=False), sa.Column("role", sa.String(20), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("must_change_password", sa.Boolean(), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("login_id"))
    op.create_index("ix_user_login_id", "user", ["login_id"], unique=False)
    op.create_index("uq_user_login_id_lower", "user", [sa.text("lower(login_id)")], unique=True)
    op.create_table("document",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("category", sa.String(10), nullable=False),
        sa.Column("document_no", sa.String(100), nullable=False), sa.Column("title", sa.String(250), nullable=False),
        sa.Column("revision", sa.String(50), nullable=False), sa.Column("effective_date", sa.Date()),
        sa.Column("status", sa.String(20), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255)), sa.Column("stored_name", sa.String(255)),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("category", "document_no", "revision", name="uq_document_revision"))
    op.create_index("ix_document_category", "document", ["category"])
    op.create_table("audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("user.id")),
        sa.Column("actor_login_id", sa.String(80), nullable=False), sa.Column("action", sa.String(80), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False), sa.Column("target_id", sa.String(100)),
        sa.Column("detail", sa.String(500), nullable=False), sa.Column("ip_address", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_table("system_setting",
        sa.Column("id", sa.Uuid(), primary_key=True), sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("value", sa.String(500), nullable=False), sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("user.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("system_setting")
    op.drop_table("audit_log")
    op.drop_table("document")
    op.drop_table("user")
