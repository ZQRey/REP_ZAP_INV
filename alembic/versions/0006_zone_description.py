"""Room descriptions."""
from alembic import op, context
import sqlalchemy as sa
revision = "0006_zone_description"
down_revision = "0005_network_credentials"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("zones", sa.Column("description", sa.Text(), nullable=True))

def downgrade():
    if context.get_x_argument(as_dictionary=True).get("allow_destructive") != "true":
        raise RuntimeError("Dropping room descriptions requires -x allow_destructive=true")
    op.drop_column("zones", "description")
