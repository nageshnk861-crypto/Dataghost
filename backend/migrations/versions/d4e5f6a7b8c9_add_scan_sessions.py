"""add_scan_sessions

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-20 10:00:00.000000

Creates the scan_sessions table for tracking full-device scan lifecycles.
All ADD-COLUMN and CREATE-TABLE statements are guarded by existence checks so
the migration is safe to run on databases that already have scan_sessions
(e.g. if create_all() was used before Alembic was introduced).

PostgreSQL notes:
  - BOOLEAN server_default uses the string 'false' (accepted by both SQLite and Postgres).
  - No batch_alter_table needed because we are creating a new table, not altering
    an existing SQLite table.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import reflection


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)

    # ------------------------------------------------------------------ #
    # scan_sessions – one record per full-device scan run                  #
    # ------------------------------------------------------------------ #
    if not insp.has_table('scan_sessions'):
        op.create_table(
            'scan_sessions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True, index=True),
            sa.Column('scan_id', sa.String(length=64), nullable=False),
            sa.Column('device_id', sa.Integer(), sa.ForeignKey('devices.id'), nullable=False),
            sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
            # ENROLLMENT | SCHEDULED | MANUAL
            sa.Column('trigger', sa.String(length=16), nullable=False, server_default='MANUAL'),
            sa.Column('started_at', sa.DateTime(), nullable=False),
            sa.Column('finished_at', sa.DateTime(), nullable=True),
            # RUNNING | COMPLETED | FAILED | CANCELLED | INTERRUPTED
            sa.Column('status', sa.String(length=16), nullable=False, server_default='RUNNING'),
            sa.Column('files_discovered', sa.Integer(), server_default='0', nullable=True),
            sa.Column('files_scanned', sa.Integer(), server_default='0', nullable=True),
            sa.Column('files_skipped', sa.Integer(), server_default='0', nullable=True),
            sa.Column('findings_count', sa.Integer(), server_default='0', nullable=True),
            sa.Column('current_path', sa.String(length=1024), nullable=True),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
        )
        # Unique index on scan_id (lookup by UUID from agent)
        op.create_index('ix_scan_sessions_scan_id', 'scan_sessions', ['scan_id'], unique=True)
        # Composite index for "list scans for device ordered by time"
        op.create_index('ix_scan_sessions_device_started', 'scan_sessions', ['device_id', 'started_at'])
        # Index for ownership queries (user_id)
        op.create_index('ix_scan_sessions_user_id', 'scan_sessions', ['user_id'])
        # Status index for in-flight scan lookups
        op.create_index('ix_scan_sessions_status', 'scan_sessions', ['status'])
    else:
        # Table already exists (pre-Alembic create_all scenario).
        # Only add any columns that might be missing so we stay idempotent.
        existing_cols = {c['name'] for c in insp.get_columns('scan_sessions')}
        _optional_cols = [
            ('files_discovered', sa.Integer(),    '0'),
            ('files_skipped',    sa.Integer(),    '0'),
            ('findings_count',   sa.Integer(),    '0'),
            ('current_path',     sa.String(1024), None),
            ('error_message',    sa.Text(),        None),
            ('updated_at',       sa.DateTime(),    None),
        ]
        for col_name, col_type, srv_default in _optional_cols:
            if col_name not in existing_cols:
                kwargs = {'nullable': True}
                if srv_default is not None:
                    kwargs['server_default'] = sa.text(srv_default)
                op.add_column('scan_sessions', sa.Column(col_name, col_type, **kwargs))


def downgrade() -> None:
    bind = op.get_bind()
    insp = reflection.Inspector.from_engine(bind)
    if insp.has_table('scan_sessions'):
        op.drop_index('ix_scan_sessions_status',         table_name='scan_sessions')
        op.drop_index('ix_scan_sessions_user_id',        table_name='scan_sessions')
        op.drop_index('ix_scan_sessions_device_started', table_name='scan_sessions')
        op.drop_index('ix_scan_sessions_scan_id',        table_name='scan_sessions')
        op.drop_table('scan_sessions')
