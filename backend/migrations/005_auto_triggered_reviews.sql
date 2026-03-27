-- ============================================================
-- 005: 评审自动触发标记
-- ============================================================

-- 新增 auto_triggered 字段，标记评审是否由系统自动触发
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS auto_triggered boolean DEFAULT false;

-- 为 pending 状态的评审添加索引，加速查询
CREATE INDEX IF NOT EXISTS idx_reviews_pending ON reviews(project_id, status) WHERE status = 'pending';
