-- 数字人问辩视频持久化 (Defense Video Persistence) - 数据库迁移脚本
-- 变更: 新增 defense_video_tasks 表，扩展 defense_records 表
-- 需求: 1.1, 1.2, 1.3, 1.4

-- ============================================================
-- 1. defense_video_tasks 表（视频生成任务）
-- ============================================================
CREATE TABLE defense_video_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    video_type TEXT NOT NULL CHECK (video_type IN ('question', 'feedback')),
    heygen_video_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'outdated')),
    persistent_url TEXT,
    heygen_video_url TEXT,
    error_message TEXT,
    questions_hash TEXT,
    defense_record_id UUID REFERENCES defense_records(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_dvt_project_id ON defense_video_tasks(project_id);
CREATE INDEX idx_dvt_status ON defense_video_tasks(status)
    WHERE status IN ('pending', 'processing');

ALTER TABLE defense_video_tasks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own project video tasks"
    ON defense_video_tasks FOR ALL
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()))
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));

-- ============================================================
-- 2. defense_records 表扩展（反馈类型与视频任务关联）
-- ============================================================
ALTER TABLE defense_records
    ADD COLUMN feedback_type TEXT DEFAULT 'text' CHECK (feedback_type IN ('text', 'video')),
    ADD COLUMN question_video_task_id UUID REFERENCES defense_video_tasks(id),
    ADD COLUMN feedback_video_task_id UUID REFERENCES defense_video_tasks(id);
