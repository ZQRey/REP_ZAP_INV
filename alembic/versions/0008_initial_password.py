"""Require replacement of the initial administrator password."""
from alembic import op, context
import sqlalchemy as sa

revision = '0008_initial_password'
down_revision = '0007_port_learned_macs'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('app_users', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    if context.get_x_argument(as_dictionary=True).get('allow_destructive') != 'true':
        raise RuntimeError('Removing the initial password gate requires -x allow_destructive=true')
    with op.batch_alter_table('app_users') as batch:
        batch.drop_column('must_change_password')
