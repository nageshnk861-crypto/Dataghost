"""add_device_token_hash_and_scan_requested

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-16 16:30:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)

    # 1. Update devices table with device_token_hash and scan_requested
    if insp.has_table('devices'):
        dev_cols = [c['name'] for c in insp.get_columns('devices')]
        if 'device_token_hash' not in dev_cols:
            op.add_column('devices', sa.Column('device_token_hash', sa.String(length=64), nullable=True))
        if 'scan_requested' not in dev_cols:
            op.add_column('devices', sa.Column('scan_requested', sa.Boolean(), server_default=sa.text('false'), nullable=False))

        if 'auth_token' not in dev_cols:
            op.add_column('devices', sa.Column('auth_token', sa.String(length=128), nullable=True))
        # Clear legacy plaintext auth_token values to protect stored tokens
        bind.execute(sa.text("UPDATE devices SET auth_token = NULL WHERE auth_token IS NOT NULL"))

    # 2. Update enrollment_tokens table to ensure user_id exists
    if insp.has_table('enrollment_tokens'):
        tok_cols = [c['name'] for c in insp.get_columns('enrollment_tokens')]
        if 'user_id' not in tok_cols:
            op.add_column('enrollment_tokens', sa.Column('user_id', sa.Integer(), nullable=True))

    # 3. Ensure device_provisioning exists for enterprise and MDM enrollment
    if not insp.has_table('device_provisioning'):
        op.create_table(
            'device_provisioning',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('organization_id', sa.String(length=64), nullable=False, index=True),
            sa.Column('enrollment_policy_id', sa.String(length=64), nullable=False),
            sa.Column('platform', sa.String(length=32), nullable=False),
            sa.Column('status', sa.String(length=16), server_default='ACTIVE', nullable=True),
            sa.Column('provisioning_method', sa.String(length=32), server_default='AUTOMATIC_ENROLLMENT', nullable=True),
            sa.Column('bootstrap_token_hash', sa.String(length=64), unique=True, index=True, nullable=False),
            sa.Column('device_count', sa.Integer(), server_default='0', nullable=True),
            sa.Column('created_by', sa.String(length=64), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=True),
            sa.Column('last_used_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_device_provisioning_org_id_status', 'device_provisioning', ['organization_id', 'status'])
        op.create_index('ix_device_provisioning_platform', 'device_provisioning', ['platform'])

    # 4. Ensure device_identity exists for cryptographic device attestation
    if not insp.has_table('device_identity'):
        op.create_table(
            'device_identity',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('device_id', sa.String(length=32), unique=True, index=True, nullable=False),
            sa.Column('platform', sa.String(length=32), nullable=False),
            sa.Column('public_key', sa.Text(), nullable=False),
            sa.Column('attestation_data', sa.JSON(), nullable=True),
            sa.Column('enrollment_code', sa.String(length=16), unique=True, index=True, nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        op.create_index('ix_device_identity_platform', 'device_identity', ['platform'])

    # 5. Backfill: Find admin user and assign ownerless devices (NULL user_id)
    if insp.has_table('users') and insp.has_table('devices'):
        admin_res = bind.execute(sa.text("SELECT id FROM users WHERE role = 'admin' OR username = 'admin' ORDER BY id ASC LIMIT 1")).fetchone()
        admin_id = admin_res[0] if admin_res else 1
        bind.execute(sa.text("UPDATE devices SET user_id = :aid WHERE user_id IS NULL"), {"aid": admin_id})


def downgrade() -> None:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)

    if insp.has_table('devices'):
        dev_cols = [c['name'] for c in insp.get_columns('devices')]
        if 'scan_requested' in dev_cols:
            op.drop_column('devices', 'scan_requested')
        if 'device_token_hash' in dev_cols:
            op.drop_column('devices', 'device_token_hash')

    if insp.has_table('enrollment_tokens'):
        tok_cols = [c['name'] for c in insp.get_columns('enrollment_tokens')]
        if 'user_id' in tok_cols:
            op.drop_column('enrollment_tokens', 'user_id')
