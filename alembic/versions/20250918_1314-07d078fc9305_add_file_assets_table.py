"""add_file_assets_table

Revision ID: 07d078fc9305
Revises: 77a956bb2aba
Create Date: 2025-09-18 13:14:20.665798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '07d078fc9305'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create file_assets table
    op.create_table(
        'file_assets',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),
        sa.Column('owner_id', sa.Integer(), nullable=True, comment='归属用户ID（可为空）'),
        sa.Column('storage_type', sa.String(length=16), nullable=False, server_default='local', comment='存储类型：local/s3/oss'),
        sa.Column('bucket', sa.String(length=255), nullable=True, comment='存储桶/容器名称'),
        sa.Column('region', sa.String(length=64), nullable=True, comment='区域名（可为空）'),
        sa.Column('key', sa.String(length=512), nullable=False, comment='对象存储中的Key（路径）'),
        sa.Column('size', sa.BigInteger(), nullable=False, server_default='0', comment='文件大小（字节）'),
        sa.Column('etag', sa.String(length=64), nullable=True, comment='存储返回的ETag/校验值'),
        sa.Column('content_type', sa.String(length=100), nullable=True, comment='MIME类型'),
        sa.Column('original_filename', sa.String(length=255), nullable=True, comment='原始文件名'),
        sa.Column('kind', sa.String(length=50), nullable=True, comment='业务分类，如 avatar/document'),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false', comment='是否公共可读'),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default=sa.text("'{}'::jsonb"), comment='扩展元数据（JSON）'),
        sa.Column('url', sa.String(length=1024), nullable=True, comment='公共/CDN URL快照（可选）'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active', comment='文件状态：pending/active/deleted'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='更新时间'),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True, comment='删除时间（软删除）'),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('storage_type', 'bucket', 'key', name='uq_storage_bucket_key'),
        comment='文件资源表，记录对象存储中的文件元数据'
    )
    
    # Create indexes
    op.create_index('ix_file_assets_created_at', 'file_assets', ['created_at'], unique=False, postgresql_using='btree')
    op.create_index('ix_file_assets_owner_created', 'file_assets', ['owner_id', 'created_at'], unique=False)
    
    # Add table comment
    op.execute("COMMENT ON TABLE file_assets IS '文件资源表，记录对象存储中的文件元数据'")
    
    # Add column comments
    op.execute("COMMENT ON COLUMN file_assets.owner_id IS '归属用户ID（可为空）'")
    op.execute("COMMENT ON COLUMN file_assets.storage_type IS '存储类型：local/s3/oss'")
    op.execute("COMMENT ON COLUMN file_assets.bucket IS '存储桶/容器名称'")
    op.execute("COMMENT ON COLUMN file_assets.region IS '区域名（可为空）'")
    op.execute("COMMENT ON COLUMN file_assets.key IS '对象存储中的Key（路径）'")
    op.execute("COMMENT ON COLUMN file_assets.size IS '文件大小（字节）'")
    op.execute("COMMENT ON COLUMN file_assets.etag IS '存储返回的ETag/校验值'")
    op.execute("COMMENT ON COLUMN file_assets.content_type IS 'MIME类型'")
    op.execute("COMMENT ON COLUMN file_assets.original_filename IS '原始文件名'")
    op.execute("COMMENT ON COLUMN file_assets.kind IS '业务分类，如 avatar/document'")
    op.execute("COMMENT ON COLUMN file_assets.is_public IS '是否公共可读'")
    op.execute("COMMENT ON COLUMN file_assets.metadata IS '扩展元数据（JSON）'")
    op.execute("COMMENT ON COLUMN file_assets.url IS '公共/CDN URL快照（可选）'")
    op.execute("COMMENT ON COLUMN file_assets.status IS '文件状态：pending/active/deleted'")
    op.execute("COMMENT ON COLUMN file_assets.created_at IS '创建时间'")
    op.execute("COMMENT ON COLUMN file_assets.updated_at IS '更新时间'")
    op.execute("COMMENT ON COLUMN file_assets.deleted_at IS '删除时间（软删除）'")


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_file_assets_owner_created', table_name='file_assets')
    op.drop_index('ix_file_assets_created_at', table_name='file_assets', postgresql_using='btree')
    
    # Drop table
    op.drop_table('file_assets')
