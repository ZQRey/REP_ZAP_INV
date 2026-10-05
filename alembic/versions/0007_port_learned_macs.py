"""Preserve all learned MAC addresses per switch port."""
from alembic import op, context
import sqlalchemy as sa
revision = "0007_port_learned_macs"
down_revision = "0006_zone_description"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("switch_ports", sa.Column("learned_macs", sa.JSON(), nullable=False, server_default="[]"))
    with op.batch_alter_table("switch_ports") as batch:
        batch.alter_column("learned_macs", server_default=None)

def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_destructive") != "true":
        raise RuntimeError("Dropping learned MAC tables requires -x allow_destructive=true")
    with op.batch_alter_table("switch_ports") as batch:
        batch.drop_column("learned_macs")
