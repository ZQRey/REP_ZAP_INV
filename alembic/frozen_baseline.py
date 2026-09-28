"""Immutable schema snapshot of main c07e978; do not import live models here."""
import sqlalchemy as sa

def schema():
    metadata = sa.MetaData()
    sa.Table('ad_users', metadata,
    sa.Column('samaccountname', sa.String(length=100), nullable=False),
    sa.Column('display_name', sa.String(length=255), nullable=False),
    sa.Column('department', sa.String(length=255), nullable=True),
    sa.Column('cabinet', sa.String(length=100), nullable=True),
    sa.Column('phone', sa.String(length=100), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('samaccountname')
    )
    sa.Index('ix_ad_users_display_name', metadata.tables['ad_users'].c['display_name'], unique=False)
    sa.Index('ix_ad_users_samaccountname', metadata.tables['ad_users'].c['samaccountname'], unique=False)
    sa.Table('branches', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('it_office', sa.String(length=255), nullable=True),
    sa.Column('network_subnets', sa.JSON(), nullable=True),
    sa.Column('wa_message_template', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_branches_name', metadata.tables['branches'].c['name'], unique=True)
    sa.Table('cartridge_models', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('vendor', sa.String(length=100), nullable=True),
    sa.Column('resource_pages', sa.Integer(), nullable=True),
    sa.Column('compatible_printers', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_cartridge_models_name', metadata.tables['cartridge_models'].c['name'], unique=True)
    sa.Table('equipment_models', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=True),
    sa.Column('vendor', sa.String(length=100), nullable=True),
    sa.Column('specs_template', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_equipment_models_name', metadata.tables['equipment_models'].c['name'], unique=True)
    sa.Table('system_settings', metadata,
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=True),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
    sa.Index('ix_system_settings_key', metadata.tables['system_settings'].c['key'], unique=False)
    sa.Table('app_users', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('username', sa.String(length=100), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=True),
    sa.Column('auth_type', sa.String(length=20), nullable=True),
    sa.Column('role', sa.String(length=20), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('branch_id', sa.Integer(), nullable=True),
    sa.Column('wa_instance_name', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_app_users_username', metadata.tables['app_users'].c['username'], unique=True)
    sa.Table('batches', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('act_number', sa.String(length=100), nullable=False),
    sa.Column('vendor_name', sa.String(length=255), nullable=False),
    sa.Column('branch_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_batches_act_number', metadata.tables['batches'].c['act_number'], unique=True)
    sa.Index('ix_batches_branch_id', metadata.tables['batches'].c['branch_id'], unique=False)
    sa.Table('cartridges', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('marker_label', sa.String(length=100), nullable=False),
    sa.Column('qr_code', sa.String(length=100), nullable=True),
    sa.Column('model', sa.String(length=100), nullable=False),
    sa.Column('cabinet', sa.String(length=100), nullable=False),
    sa.Column('status', sa.Enum('IN_USE', 'PENDING_VENDOR', 'AT_VENDOR', 'READY_FOR_PICKUP', name='cartridgestatus'), nullable=False),
    sa.Column('branch_id', sa.Integer(), nullable=True),
    sa.Column('current_user_id', sa.String(length=100), nullable=True),
    sa.Column('condition', sa.String(length=20), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['current_user_id'], ['ad_users.samaccountname'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_cartridges_branch_id', metadata.tables['cartridges'].c['branch_id'], unique=False)
    sa.Index('ix_cartridges_marker_label', metadata.tables['cartridges'].c['marker_label'], unique=True)
    sa.Index('ix_cartridges_qr_code', metadata.tables['cartridges'].c['qr_code'], unique=True)
    sa.Index('ix_cartridges_status', metadata.tables['cartridges'].c['status'], unique=False)
    sa.Table('floors', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('branch_id', sa.Integer(), nullable=False),
    sa.Column('floor_number', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('map_image_url', sa.String(length=500), nullable=True),
    sa.Column('scale_pixels_per_meter', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('repair_batches', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('act_number', sa.String(length=100), nullable=False),
    sa.Column('vendor_name', sa.String(length=255), nullable=False),
    sa.Column('branch_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_repair_batches_act_number', metadata.tables['repair_batches'].c['act_number'], unique=True)
    sa.Index('ix_repair_batches_branch_id', metadata.tables['repair_batches'].c['branch_id'], unique=False)
    sa.Table('spare_parts_warehouse', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('branch_id', sa.Integer(), nullable=False),
    sa.Column('category', sa.String(length=100), nullable=False),
    sa.Column('item_name', sa.String(length=200), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('min_threshold', sa.Integer(), nullable=True),
    sa.Column('unit_price', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('audit_logs', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('target_module', sa.String(length=50), nullable=False),
    sa.Column('target_entity', sa.String(length=100), nullable=True),
    sa.Column('entity_id', sa.String(length=100), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['app_users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_audit_logs_created_at', metadata.tables['audit_logs'].c['created_at'], unique=False)
    sa.Table('batch_items', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('cartridge_id', sa.Integer(), nullable=False),
    sa.Column('action_required', sa.String(length=100), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['cartridge_id'], ['cartridges.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('cable_paths', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('floor_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=True),
    sa.Column('path_vectors', sa.JSON(), nullable=False),
    sa.Column('max_capacity', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('history_logs', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('cartridge_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('user_name', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['cartridge_id'], ['cartridges.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_history_logs_cartridge_id', metadata.tables['history_logs'].c['cartridge_id'], unique=False)
    sa.Index('ix_history_logs_timestamp', metadata.tables['history_logs'].c['timestamp'], unique=False)
    sa.Table('zones', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('floor_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('zone_type', sa.String(length=50), nullable=True),
    sa.Column('polygon_coords', sa.JSON(), nullable=False),
    sa.Column('fill_color', sa.String(length=50), nullable=True),
    sa.Column('border_color', sa.String(length=50), nullable=True),
    sa.Column('responsible_person', sa.String(length=200), nullable=True),
    sa.Column('room_number', sa.String(length=50), nullable=True),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('assets', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('inventory_number', sa.String(length=100), nullable=False),
    sa.Column('serial_number', sa.String(length=100), nullable=True),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('asset_type', sa.Enum('WORKSTATION', 'LAPTOP', 'MONITOR', 'PRINTER', 'SERVER', 'SWITCH', 'UPS', 'OTHER', name='assettype'), nullable=False),
    sa.Column('status', sa.Enum('AT_WORKPLACE', 'PENDING_SC', 'AT_SC', 'RETURNED_IT', 'DECOMMISSIONED', name='assetstatus'), nullable=False),
    sa.Column('condition', sa.Enum('WORKING', 'BROKEN', name='assetcondition'), nullable=False),
    sa.Column('ad_guid', sa.String(length=100), nullable=True),
    sa.Column('hostname', sa.String(length=150), nullable=True),
    sa.Column('os_name', sa.String(length=150), nullable=True),
    sa.Column('last_logon', sa.DateTime(), nullable=True),
    sa.Column('ip_address', sa.String(length=50), nullable=True),
    sa.Column('mac_address', sa.String(length=50), nullable=True),
    sa.Column('branch_id', sa.Integer(), nullable=True),
    sa.Column('cabinet', sa.String(length=100), nullable=True),
    sa.Column('current_user_id', sa.String(length=100), nullable=True),
    sa.Column('floor_id', sa.Integer(), nullable=True),
    sa.Column('zone_id', sa.Integer(), nullable=True),
    sa.Column('coords_x', sa.Float(), nullable=True),
    sa.Column('coords_y', sa.Float(), nullable=True),
    sa.Column('specs', sa.JSON(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['branch_id'], ['branches.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['current_user_id'], ['ad_users.samaccountname'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['floor_id'], ['floors.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_assets_ad_guid', metadata.tables['assets'].c['ad_guid'], unique=False)
    sa.Index('ix_assets_asset_type', metadata.tables['assets'].c['asset_type'], unique=False)
    sa.Index('ix_assets_branch_id', metadata.tables['assets'].c['branch_id'], unique=False)
    sa.Index('ix_assets_condition', metadata.tables['assets'].c['condition'], unique=False)
    sa.Index('ix_assets_floor_id', metadata.tables['assets'].c['floor_id'], unique=False)
    sa.Index('ix_assets_hostname', metadata.tables['assets'].c['hostname'], unique=False)
    sa.Index('ix_assets_inventory_number', metadata.tables['assets'].c['inventory_number'], unique=True)
    sa.Index('ix_assets_serial_number', metadata.tables['assets'].c['serial_number'], unique=False)
    sa.Index('ix_assets_status', metadata.tables['assets'].c['status'], unique=False)
    sa.Index('ix_assets_zone_id', metadata.tables['assets'].c['zone_id'], unique=False)
    sa.Table('equipment_history_logs', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('user_name', sa.String(length=255), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Index('ix_equipment_history_logs_asset_id', metadata.tables['equipment_history_logs'].c['asset_id'], unique=False)
    sa.Index('ix_equipment_history_logs_timestamp', metadata.tables['equipment_history_logs'].c['timestamp'], unique=False)
    sa.Table('network_switches', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('ip_address', sa.String(length=50), nullable=False),
    sa.Column('management_type', sa.String(length=50), nullable=True),
    sa.Column('mgmt_port', sa.Integer(), nullable=True),
    sa.Column('username', sa.String(length=100), nullable=True),
    sa.Column('password', sa.String(length=255), nullable=True),
    sa.Column('snmp_community', sa.String(length=100), nullable=True),
    sa.Column('model', sa.String(length=150), nullable=True),
    sa.Column('total_ports', sa.Integer(), nullable=True),
    sa.Column('extra_params', sa.JSON(), nullable=True),
    sa.Column('last_poll_status', sa.String(length=20), nullable=True),
    sa.Column('last_poll_message', sa.String(length=500), nullable=True),
    sa.Column('last_polled_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('asset_id')
    )
    sa.Table('repair_batch_items', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('asset_id', sa.Integer(), nullable=False),
    sa.Column('reported_issue', sa.Text(), nullable=True),
    sa.Column('diagnostic_result', sa.Text(), nullable=True),
    sa.Column('work_performed', sa.Text(), nullable=True),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('returned_at', sa.DateTime(), nullable=True),
    sa.Column('installed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['batch_id'], ['repair_batches.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('repair_parts_used', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('repair_item_id', sa.Integer(), nullable=False),
    sa.Column('part_name', sa.String(length=200), nullable=False),
    sa.Column('serial_number', sa.String(length=100), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('cost', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.ForeignKeyConstraint(['repair_item_id'], ['repair_batch_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    sa.Table('switch_ports', metadata,
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('switch_id', sa.Integer(), nullable=False),
    sa.Column('port_number', sa.Integer(), nullable=False),
    sa.Column('port_speed', sa.String(length=50), nullable=True),
    sa.Column('vlan_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('cabinet', sa.String(length=100), nullable=True),
    sa.Column('socket_label', sa.String(length=100), nullable=True),
    sa.Column('zone_id', sa.Integer(), nullable=True),
    sa.Column('last_mac', sa.String(length=50), nullable=True),
    sa.Column('last_ip', sa.String(length=50), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('connected_asset_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['connected_asset_id'], ['assets.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['switch_id'], ['network_switches.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['zone_id'], ['zones.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    return metadata
