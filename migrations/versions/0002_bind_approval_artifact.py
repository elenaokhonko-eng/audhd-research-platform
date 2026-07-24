"""Bind approvals to stored artifacts."""
from alembic import op
import sqlalchemy as sa

revision = "0002_bind_approval_artifact"
down_revision = "0001_platform_foundation"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("approvals")}
    if "artifact_id" not in columns:
        op.add_column("approvals", sa.Column("artifact_id", sa.Uuid(), nullable=True))
        op.create_index("ix_approvals_artifact_id", "approvals", ["artifact_id"])
        op.create_foreign_key("fk_approvals_artifact_id", "approvals", "artifacts", ["artifact_id"], ["id"])


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("approvals")}
    if "artifact_id" in columns:
        op.drop_constraint("fk_approvals_artifact_id", "approvals", type_="foreignkey")
        op.drop_index("ix_approvals_artifact_id", table_name="approvals")
        op.drop_column("approvals", "artifact_id")
