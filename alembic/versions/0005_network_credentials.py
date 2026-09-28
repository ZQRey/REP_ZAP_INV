"""Encrypt persisted network credentials.

Revision ID: 0005_network_credentials
Revises: 0004_notification_outbox
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_network_credentials"
down_revision = "0004_notification_outbox"
branch_labels = None
depends_on = None


def upgrade():
    # Ciphertext is longer than legacy plaintext fields. Encryption itself is
    # performed by an explicit deployment command/application pass because Alembic
    # must not receive the production encryption key.
    op.alter_column("network_switches", "password", type_=sa.String(1000), existing_type=sa.String(255))
    op.alter_column("network_switches", "snmp_community", type_=sa.String(1000), existing_type=sa.String(100))


def downgrade():
    raise RuntimeError("0005 stores encrypted credentials and cannot be safely narrowed automatically")
