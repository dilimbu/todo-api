"""add_task_user_id

Revision ID: ecfd95801a5c
Revises: 03dd29843910
Create Date: 2026-08-03 18:16:58.879018
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "ecfd95801a5c"
down_revision: Union[str, Sequence[str], None] = "03dd29843910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    user_id column already exists (nullable) from the failed first attempt.
    Do NOT add_column again — that would error with duplicate column.
    """
    # 1) Backfill any NULL owners
    op.execute(
        """
        UPDATE tasks
        SET user_id = (SELECT id FROM users ORDER BY id LIMIT 1)
        WHERE user_id IS NULL
        """
    )
    # If you prefer wiping old global tasks instead:
    # op.execute("DELETE FROM tasks WHERE user_id IS NULL")

    # 2) SQLite-safe: rebuild table to set NOT NULL + FK + index
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_tasks_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )
        batch_op.create_index("ix_tasks_user_id", ["user_id"])


def downgrade() -> None:
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_tasks_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_tasks_user_id")
        batch_op.drop_column("user_id")