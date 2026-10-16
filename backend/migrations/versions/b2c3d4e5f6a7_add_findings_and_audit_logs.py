"""add_findings_and_audit_logs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-16 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Add new columns to scan_logs if not already present
    with op.batch_alter_table('scan_logs') as batch_op:
        batch_op.add_column(sa.Column('scan_id', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=16), server_default='COMPLETED', nullable=True))
        batch_op.add_column(sa.Column('file_size', sa.Integer(), nullable=True))
        batch_op.create_index('ix_scan_logs_scan_id', ['scan_id'], unique=True)
        batch_op.create_index('ix_scan_logs_user_id', ['user_id'], unique=False)
        batch_op.create_foreign_key('fk_scan_logs_user', 'users', ['user_id'], ['id'])

    # 2. Create findings table
    op.create_table(
        'findings',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('scan_log_id', sa.Integer(), sa.ForeignKey('scan_logs.id'), nullable=True, index=True),
        sa.Column('scan_id', sa.String(length=64), nullable=True, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True, index=True),
        sa.Column('device_id', sa.String(length=64), nullable=True, index=True),
        sa.Column('file_name', sa.String(length=512), nullable=True),
        sa.Column('file_hash', sa.String(length=128), nullable=True),
        sa.Column('detector_id', sa.String(length=64), nullable=True),
        sa.Column('rule_id', sa.String(length=128), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=True, index=True),
        sa.Column('severity', sa.String(length=16), server_default='LOW', index=True),
        sa.Column('confidence', sa.Float(), server_default='1.0'),
        sa.Column('risk_score', sa.Integer(), server_default='0'),
        sa.Column('line_number', sa.Integer(), server_default='0'),
        sa.Column('column_number', sa.Integer(), server_default='0'),
        sa.Column('char_start', sa.Integer(), server_default='0'),
        sa.Column('char_end', sa.Integer(), server_default='0'),
        sa.Column('evidence_redacted', sa.Text(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('remediation', sa.Text(), nullable=True),
        sa.Column('fingerprint', sa.String(length=64), nullable=True, index=True),
        sa.Column('status', sa.String(length=16), server_default='OPEN', index=True),
        sa.Column('first_seen_at', sa.DateTime(), nullable=True),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
        sa.Column('occurrence_count', sa.Integer(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_findings_fingerprint_device', 'findings', ['fingerprint', 'device_id'])
    op.create_index('ix_findings_user_status', 'findings', ['user_id', 'status'])
    op.create_index('ix_findings_severity_status', 'findings', ['severity', 'status'])

    # 3. Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('actor_username', sa.String(length=64), nullable=True),
        sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False, index=True),
        sa.Column('resource_type', sa.String(length=32), nullable=True, index=True),
        sa.Column('resource_id', sa.String(length=128), nullable=True),
        sa.Column('result', sa.String(length=16), server_default='SUCCESS'),
        sa.Column('ip_address', sa.String(length=64), nullable=True),
        sa.Column('request_id', sa.String(length=64), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True, index=True),
    )
    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'])


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('findings')
    with op.batch_alter_table('scan_logs') as batch_op:
        batch_op.drop_constraint('fk_scan_logs_user', type_='foreignkey')
        batch_op.drop_index('ix_scan_logs_user_id')
        batch_op.drop_index('ix_scan_logs_scan_id')
        batch_op.drop_column('file_size')
        batch_op.drop_column('status')
        batch_op.drop_column('organization_id')
        batch_op.drop_column('user_id')
        batch_op.drop_column('scan_id')
