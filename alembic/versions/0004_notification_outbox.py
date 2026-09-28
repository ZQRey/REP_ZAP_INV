"""Add durable notification outbox.

Revision ID: 0004_notification_outbox
Revises: 0003_integrity_numbering
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_notification_outbox"
down_revision = "0003_integrity_numbering"
branch_labels = None
depends_on = None


def upgrade():
    status_enum = sa.Enum("PENDING", "PROCESSING", "SENT", "RETRY", "FAILED", "DEAD", name="notificationstatus")
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("cartridge_id", sa.Integer(), sa.ForeignKey("cartridges.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("recipient", sa.String(100), nullable=False),
        sa.Column("template", sa.String(100), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", status_enum, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("instance_name", sa.String(100), nullable=True),
        sa.CheckConstraint("attempts >= 0", name="ck_notifications_attempts"),
        sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
    )
    op.create_index("ix_notifications_dispatch", "notifications", ["status", "next_attempt_at"])
    op.create_index("ix_notifications_branch_id", "notifications", ["branch_id"])


def downgrade():
    op.drop_index("ix_notifications_branch_id", table_name="notifications")
    op.drop_index("ix_notifications_dispatch", table_name="notifications")
    op.drop_table("notifications")
    sa.Enum(name="notificationstatus").drop(op.get_bind(), checkfirst=True)
