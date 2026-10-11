"""add_device_user_fk

Revision ID: a1b2c3d4e5f6
Revises: 9f7215996874
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '9f7215996874'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Backfill NULL user_id to admin user (1) before enforcing constraints
    op.execute("UPDATE devices SET user_id = 1 WHERE user_id IS NULL OR user_id = ''")
    op.execute("DROP INDEX IF EXISTS idx_device_user_id")

    # 2. Add foreign key and index
    with op.batch_alter_table('devices') as batch_op:
        batch_op.alter_column('user_id',
                              existing_type=sa.String(length=64),
                              type_=sa.Integer(),
                              nullable=False)
        batch_op.create_foreign_key('fk_device_user', 'users', ['user_id'], ['id'])
        batch_op.create_index('idx_device_user_id', ['user_id'], unique=False)

    # 3. Add user_id to enrollment_tokens if not present
    with op.batch_alter_table('enrollment_tokens') as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_enrollment_tokens_user', 'users', ['user_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('enrollment_tokens') as batch_op:
        batch_op.drop_column('user_id')

    with op.batch_alter_table('devices') as batch_op:
        batch_op.drop_index('idx_device_user_id')
        batch_op.drop_constraint('fk_device_user', type_='foreignkey')
        batch_op.alter_column('user_id',
                              existing_type=sa.Integer(),
                              type_=sa.String(length=64),
                              nullable=True)
