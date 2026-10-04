"""telegram delivery and emergency alarms

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-04 14:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('notifications') as batch:
        batch.add_column(sa.Column('urgent', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column('data', sa.JSON(), nullable=True))
        batch.add_column(sa.Column('feed', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column('telegram_sent_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_index('ix_notifications_telegram_sent_at', ['telegram_sent_at'])
    with op.batch_alter_table('orders') as batch:
        batch.add_column(sa.Column('alarm_repeated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders') as batch:
        batch.drop_column('alarm_repeated_at')
    with op.batch_alter_table('notifications') as batch:
        batch.drop_index('ix_notifications_telegram_sent_at')
        batch.drop_column('telegram_sent_at')
        batch.drop_column('feed')
        batch.drop_column('data')
        batch.drop_column('urgent')
