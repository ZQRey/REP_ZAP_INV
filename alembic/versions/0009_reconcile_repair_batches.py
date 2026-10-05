"""Close existing repair acts whose positions have all been returned."""
from alembic import op

revision = '0009_reconcile_repair_batches'
down_revision = '0008_initial_password'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE repair_batches
        SET status = 'closed', closed_at = COALESCE(closed_at,
            (SELECT MAX(returned_at) FROM repair_batch_items WHERE batch_id = repair_batches.id))
        WHERE status = 'open'
          AND EXISTS (SELECT 1 FROM repair_batch_items WHERE batch_id = repair_batches.id)
          AND NOT EXISTS (SELECT 1 FROM repair_batch_items
              WHERE batch_id = repair_batches.id AND status = 'in_repair')
    """)


def downgrade():
    # Corrected historical statuses cannot safely be distinguished from later user actions.
    pass
