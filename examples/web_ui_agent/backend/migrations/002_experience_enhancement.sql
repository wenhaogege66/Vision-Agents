-- AI评委系统体验增强 - 数据库迁移脚本
-- 新增表: project_profiles, project_tags, project_tag_associations, stage_configs
-- 需求: 13.1 (AI项目简介), 14.1 (自定义标签), 10.1 (进度时间线日期)

-- ============================================================
-- 1. project_profiles 表（AI提取的项目简介）
-- ============================================================
CREATE TABLE project_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  team_intro TEXT,                        -- 团队介绍
  domain TEXT,                            -- 所属领域
  startup_status TEXT,                    -- 创业状态
  achievements TEXT,                      -- 已有成果
  product_links TEXT,                     -- 产品链接
  next_goals TEXT,                        -- 下一步目标
  is_ai_generated BOOLEAN DEFAULT TRUE,   -- 是否AI生成（用户编辑后设为false）
  source_material_versions JSONB,         -- 提取时使用的材料版本 {"bp": 1, "text_ppt": 2}
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id)
);

CREATE INDEX idx_project_profiles_project ON project_profiles(project_id);

ALTER TABLE project_profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own project profiles" ON project_profiles
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_profiles.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can insert own project profiles" ON project_profiles
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_profiles.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can update own project profiles" ON project_profiles
  FOR UPDATE USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_profiles.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can delete own project profiles" ON project_profiles
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_profiles.project_id AND projects.user_id = (select auth.uid()))
  );

-- ============================================================
-- 2. project_tags 表（用户自定义标签）
-- ============================================================
CREATE TABLE project_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name VARCHAR(50) NOT NULL,
  color VARCHAR(20) NOT NULL,             -- 预设颜色值，如 "#f5222d"
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, name)
);

CREATE INDEX idx_project_tags_user ON project_tags(user_id);

ALTER TABLE project_tags ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own tags" ON project_tags
  FOR SELECT USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can create own tags" ON project_tags
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);
CREATE POLICY "Users can update own tags" ON project_tags
  FOR UPDATE USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can delete own tags" ON project_tags
  FOR DELETE USING ((select auth.uid()) = user_id);

-- ============================================================
-- 3. project_tag_associations 表（项目-标签多对多关联）
-- ============================================================
CREATE TABLE project_tag_associations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  tag_id UUID NOT NULL REFERENCES project_tags(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(project_id, tag_id)
);

CREATE INDEX idx_tag_associations_project ON project_tag_associations(project_id);
CREATE INDEX idx_tag_associations_tag ON project_tag_associations(tag_id);

ALTER TABLE project_tag_associations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own tag associations" ON project_tag_associations
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_tag_associations.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can insert own tag associations" ON project_tag_associations
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_tag_associations.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can delete own tag associations" ON project_tag_associations
  FOR DELETE USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_tag_associations.project_id AND projects.user_id = (select auth.uid()))
  );

-- ============================================================
-- 4. stage_configs 表（赛事阶段日期配置）
-- ============================================================
CREATE TABLE stage_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  competition VARCHAR(100) NOT NULL,
  track VARCHAR(100) NOT NULL,
  stage VARCHAR(50) NOT NULL,             -- 如 "school_text", "province_presentation"
  stage_date DATE,                         -- 阶段日期
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(competition, track, stage)
);

CREATE INDEX idx_stage_configs_competition_track ON stage_configs(competition, track);

ALTER TABLE stage_configs ENABLE ROW LEVEL SECURITY;

-- stage_configs 为全局配置，所有已认证用户可读
CREATE POLICY "Authenticated users can view stage configs" ON stage_configs
  FOR SELECT USING (auth.uid() IS NOT NULL);
