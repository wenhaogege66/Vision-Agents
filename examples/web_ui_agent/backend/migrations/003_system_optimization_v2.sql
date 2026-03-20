-- AI评委系统优化V2 - 数据库迁移脚本
-- 变更: reviews 表新增字段, 新增 api_timing_logs 表
-- 需求: 3.1 (评审记录所选材料), 4.3 (PPT视觉评审结果),
--       6.3 (STT转录文本), 8.1 (路演者评价), 11.6 (API耗时日志)

-- ============================================================
-- 1. reviews 表扩展字段
-- ============================================================

-- 新增 selected_materials 字段（存储用户选择的材料类型列表）
ALTER TABLE reviews ADD COLUMN selected_materials text[] DEFAULT NULL;

-- 新增 ppt_visual_review 字段（存储 PPT 视觉评审结果 JSON）
ALTER TABLE reviews ADD COLUMN ppt_visual_review jsonb DEFAULT NULL;

-- 新增 presenter_evaluation 字段（存储路演者评价 JSON）
ALTER TABLE reviews ADD COLUMN presenter_evaluation jsonb DEFAULT NULL;

-- 新增 stt_transcript 字段（存储 STT 转录文本）
ALTER TABLE reviews ADD COLUMN stt_transcript text DEFAULT NULL;

-- ============================================================
-- 2. api_timing_logs 表（可选，用于持久化 API 耗时日志）
-- ============================================================
CREATE TABLE api_timing_logs (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    api_path text NOT NULL,
    method text NOT NULL,
    total_ms numeric NOT NULL,
    stages jsonb DEFAULT '[]',
    status_code int,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX idx_api_timing_logs_created ON api_timing_logs(created_at DESC);
CREATE INDEX idx_api_timing_logs_path ON api_timing_logs(api_path);

ALTER TABLE api_timing_logs ENABLE ROW LEVEL SECURITY;

-- api_timing_logs 为系统日志，所有已认证用户可读
CREATE POLICY "Authenticated users can view api timing logs" ON api_timing_logs
  FOR SELECT USING (auth.uid() IS NOT NULL);

-- 后端服务写入耗时日志（通过 service_role key）
CREATE POLICY "Service can insert api timing logs" ON api_timing_logs
  FOR INSERT WITH CHECK (true);
