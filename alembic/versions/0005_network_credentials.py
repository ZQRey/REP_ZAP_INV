"""Encrypt persisted network credentials.

Revision ID: 0005_network_credentials
Revises: 0004_notification_outbox
"""
from alembic import context, op
import sqlalchemy as sa

revision = "0005_network_credentials"
down_revision = "0004_notification_outbox"
branch_labels = None
depends_on = None


def upgrade():
    # Ciphertext is longer than legacy plaintext fields. Encryption itself is
    # performed by an explicit deployment command/application pass because Alembic
    # must not receive the production encryption key.
    #
    # batch_alter_table keeps the same PostgreSQL DDL semantics while allowing
    # SQLite-based CI/test databases to rebuild the table safely.
    with op.batch_alter_table("network_switches") as batch:
        batch.alter_column(
            "password",
            type_=sa.String(1000),
            existing_type=sa.String(255),
            existing_nullable=True,
        )
        batch.alter_column(
            "snmp_community",
            type_=sa.String(1000),
            existing_type=sa.String(100),
            existing_nullable=True,
        )


def _assert_safe_to_narrow(bind):
    row = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM network_switches
            WHERE length(password) > 255
               OR length(snmp_community) > 100
            LIMIT 1
            """
        )
    ).first()
    if row:
        raise RuntimeError(
            "0005 downgrade would truncate encrypted network credentials; "
            "rotate/clear oversized values before retrying"
        )


def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_destructive") != "true":
        raise RuntimeError(
            "0005 stores encrypted credentials and cannot be safely narrowed automatically; "
            "requires -x allow_destructive=true"
        )

    bind = op.get_bind()
    _assert_safe_to_narrow(bind)

    with op.batch_alter_table("network_switches") as batch:
        batch.alter_column(
            "password",
            type_=sa.String(255),
            existing_type=sa.String(1000),
            existing_nullable=True,
        )
        batch.alter_column(
            "snmp_community",
            type_=sa.String(100),
            existing_type=sa.String(1000),
            existing_nullable=True,
        )
