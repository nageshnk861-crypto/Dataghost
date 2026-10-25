"""create_incident_and_scan_tables

Revision ID: 9f7215996874
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = '9f7215996874'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # If starting on a completely empty database, create base tables first
    bind = op.get_bind()
    insp = sa.inspect(bind)
    table_names = set(insp.get_table_names())

    if "users" not in table_names:
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('username', sa.String(length=64), unique=True, index=True, nullable=False),
            sa.Column('hashed_password', sa.String(length=128), nullable=False),
            sa.Column('role', sa.String(length=16), server_default='analyst', nullable=False),
            sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if "devices" not in table_names:
        op.create_table(
            'devices',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('device_id', sa.String(length=64), unique=True, index=True, nullable=False),
            sa.Column('device_name', sa.String(length=128), nullable=False),
            sa.Column('os_type', sa.String(length=64), nullable=True),
            sa.Column('platform', sa.String(length=32), server_default='Windows', nullable=True),
            sa.Column('agent_version', sa.String(length=32), nullable=True),
            sa.Column('ip_address', sa.String(length=64), nullable=True),
            sa.Column('mac_address', sa.String(length=64), nullable=True),
            sa.Column('status', sa.String(length=16), server_default='OFFLINE', nullable=True),
            sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True),
            sa.Column('user_id', sa.String(length=64), nullable=True),
            sa.Column('last_seen', sa.DateTime(), nullable=True),
            sa.Column('registered_at', sa.DateTime(), nullable=True),
            sa.Column('enrolled_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.Column('policy_version', sa.String(length=32), nullable=True),
            sa.Column('risk_score', sa.Integer(), server_default='0', nullable=True),
            sa.Column('files_scanned', sa.Integer(), server_default='0', nullable=True),
            sa.Column('incidents_count', sa.Integer(), server_default='0', nullable=True),
        )

    if "enrollment_tokens" not in table_names:
        op.create_table(
            'enrollment_tokens',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('token_hash', sa.String(length=64), unique=True, index=True, nullable=False),
            sa.Column('device_id', sa.String(length=64), nullable=True),
            sa.Column('organization_id', sa.String(length=64), server_default='default-org', nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('used', sa.Boolean(), server_default=sa.text('false'), nullable=False),
            sa.Column('used_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
        )

    if "scan_logs" not in table_names:
        op.create_table(
            'scan_logs',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('timestamp', sa.DateTime(), nullable=True),
            sa.Column('filename', sa.String(length=512), nullable=True),
            sa.Column('file_hash', sa.String(length=128), nullable=True),
            sa.Column('classification', sa.String(length=32), nullable=True),
            sa.Column('risk_score', sa.Integer(), server_default='0', nullable=True),
            sa.Column('findings_count', sa.Integer(), server_default='0', nullable=True),
            sa.Column('device_id', sa.String(length=64), nullable=True),
        )

    if "incidents" not in table_names:
        op.create_table(
            'incidents',
            sa.Column('id', sa.Integer(), primary_key=True, index=True),
            sa.Column('incident_id', sa.String(length=32), unique=True, index=True, nullable=False),
            sa.Column('timestamp', sa.DateTime(), nullable=True, index=True),
            sa.Column('user', sa.String(length=64), nullable=True, index=True),
            sa.Column('filename', sa.String(length=512), nullable=True),
            sa.Column('file_hash', sa.String(length=128), nullable=True),
            sa.Column('classification', sa.String(length=32), nullable=True, index=True),
            sa.Column('confidence', sa.Float(), server_default='1.0', nullable=True),
            sa.Column('risk_score', sa.Integer(), server_default='0', index=True),
            sa.Column('severity', sa.String(length=16), server_default='LOW', index=True),
            sa.Column('recommended_action', sa.String(length=16), server_default='ALLOW', index=True),
            sa.Column('action_taken', sa.String(length=16), server_default='ALLOWED', nullable=True),
            sa.Column('destination', sa.String(length=32), server_default='INTERNAL', index=True),
            sa.Column('action', sa.String(length=32), server_default='READ', nullable=True),
            sa.Column('status', sa.String(length=16), server_default='OPEN', index=True, nullable=False),
            sa.Column('findings_json', sa.Text(), nullable=True),
            sa.Column('categories_json', sa.Text(), nullable=True),
            sa.Column('triggered_rules_json', sa.Text(), nullable=True),
            sa.Column('device_id', sa.String(length=64), nullable=True, index=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
    else:
        # Alter existing incidents table
        with op.batch_alter_table('incidents') as batch_op:
            batch_op.alter_column('destination',
                       existing_type=sa.VARCHAR(length=16),
                       type_=sa.String(length=32),
                       existing_nullable=True)
            batch_op.alter_column('status',
                       existing_type=sa.VARCHAR(length=16),
                       nullable=False,
                       existing_server_default=sa.text("'OPEN'"))
            batch_op.create_index(op.f('ix_incidents_classification'), ['classification'], unique=False)
            batch_op.create_index(op.f('ix_incidents_destination'), ['destination'], unique=False)
            batch_op.create_index(op.f('ix_incidents_device_id'), ['device_id'], unique=False)
            batch_op.create_index(op.f('ix_incidents_recommended_action'), ['recommended_action'], unique=False)
            batch_op.create_index(op.f('ix_incidents_risk_score'), ['risk_score'], unique=False)
            batch_op.create_index(op.f('ix_incidents_severity'), ['severity'], unique=False)
            batch_op.create_index(op.f('ix_incidents_status'), ['status'], unique=False)
            batch_op.create_index(op.f('ix_incidents_user'), ['user'], unique=False)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_incidents_user'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_status'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_severity'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_risk_score'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_recommended_action'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_device_id'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_destination'), table_name='incidents')
    op.drop_index(op.f('ix_incidents_classification'), table_name='incidents')
    op.alter_column('incidents', 'status',
               existing_type=sa.VARCHAR(length=16),
               nullable=True,
               existing_server_default=sa.text("'OPEN'"))
    op.alter_column('incidents', 'destination',
               existing_type=sa.String(length=32),
               type_=sa.VARCHAR(length=16),
               existing_nullable=True)
    # ### end Alembic commands ###
