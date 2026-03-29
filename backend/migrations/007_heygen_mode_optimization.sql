-- HeyGen 模式优化 - 数据库迁移脚本
-- 变更: 扩展 defense_video_tasks 表，支持视频复用和选项存储
-- 需求: 7.3, 7.4

-- ============================================================
-- 1. defense_video_tasks 表扩展
-- ============================================================

-- config_hash: 用于视频复用匹配（问题+avatar+voice+所有视频选项的 MD5）
ALTER TABLE defense_video_tasks
    ADD COLUMN IF NOT EXISTS config_hash TEXT;

-- avatar_type: 记录生成时使用的数字人类型
ALTER TABLE defense_video_tasks
    ADD COLUMN IF NOT EXISTS avatar_type TEXT
    CHECK (avatar_type IN ('photo_avatar', 'digital_twin'));

-- video_options: 存储完整的视频生成选项快照（JSONB）
ALTER TABLE defense_video_tasks
    ADD COLUMN IF NOT EXISTS video_options JSONB DEFAULT '{}';

-- 条件索引：加速 config_hash 复用查询（仅索引已完成的任务）
CREATE INDEX IF NOT EXISTS idx_dvt_config_hash
    ON defense_video_tasks(config_hash)
    WHERE status = 'completed';
