-- 数字人问辩 (Digital Human Defense) - 数据库迁移脚本
-- 变更: 新增 defense_questions 表和 defense_records 表
-- 需求: 10.1, 10.2, 10.3, 10.4, 10.5

-- ============================================================
-- 1. defense_questions 表（预定义评委问题）
-- ============================================================
CREATE TABLE defense_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    content TEXT NOT NULL CHECK (char_length(content) <= 40),
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_defense_questions_project_id ON defense_questions(project_id);

ALTER TABLE defense_questions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own project questions"
    ON defense_questions FOR ALL
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()))
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));

-- ============================================================
-- 2. defense_records 表（问辩记录）
-- ============================================================
CREATE TABLE defense_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id),
    questions_snapshot JSONB NOT NULL,
    user_answer_text TEXT,
    ai_feedback_text TEXT,
    answer_duration INTEGER NOT NULL DEFAULT 30,
    status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed', 'failed')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_defense_records_project_id ON defense_records(project_id);

ALTER TABLE defense_records ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own project records"
    ON defense_records FOR ALL
    USING (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()))
    WITH CHECK (project_id IN (SELECT id FROM projects WHERE user_id = auth.uid()));
