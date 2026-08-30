"""Add inactive declaration metadata attachment capability.

Revision ID: c7a9b21d4e63
Revises: 461111b60977
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7a9b21d4e63"
down_revision: Union[str, None] = "461111b60977"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broker_reports_declaration_metadata_attachment_capability",
        sa.Column("capability_id", sa.String(length=80), primary_key=True),
        sa.Column("schema_version", sa.String(length=96), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False, unique=True),
        sa.Column("actor_user_id", sa.String(length=255), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("receipt_schema_version", sa.String(length=96), nullable=False),
        sa.Column("receipt_id", sa.String(length=64), nullable=False),
        sa.Column("source_sha256", sa.String(length=64), nullable=False),
        sa.Column("intake_slot", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("issued_at", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("workspace_model_id", sa.String(length=255), nullable=True),
        sa.Column(
            "binding_sha256", sa.String(length=64), nullable=True, unique=True
        ),
        sa.Column("consumed_at", sa.BigInteger(), nullable=True),
        sa.CheckConstraint("state IN ('PENDING','CONSUMED','EXPIRED')"),
        sa.CheckConstraint("expires_at > issued_at"),
        sa.CheckConstraint(
            "(state = 'CONSUMED' AND chat_id IS NOT NULL "
            "AND message_id IS NOT NULL AND workspace_model_id IS NOT NULL "
            "AND binding_sha256 IS NOT NULL AND consumed_at IS NOT NULL) OR "
            "(state != 'CONSUMED' AND chat_id IS NULL AND message_id IS NULL "
            "AND workspace_model_id IS NULL AND binding_sha256 IS NULL "
            "AND consumed_at IS NULL)"
        ),
    )
    op.create_index(
        "ix_br_dm_attachment_owner_expiry",
        "broker_reports_declaration_metadata_attachment_capability",
        ["actor_user_id", "expires_at"],
    )
    op.create_index(
        "ix_br_dm_attachment_source_owner",
        "broker_reports_declaration_metadata_attachment_capability",
        ["source_id", "actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_br_dm_attachment_source_owner",
        table_name="broker_reports_declaration_metadata_attachment_capability",
    )
    op.drop_index(
        "ix_br_dm_attachment_owner_expiry",
        table_name="broker_reports_declaration_metadata_attachment_capability",
    )
    op.drop_table("broker_reports_declaration_metadata_attachment_capability")
