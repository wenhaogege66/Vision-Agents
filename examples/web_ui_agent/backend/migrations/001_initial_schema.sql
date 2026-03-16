-- AI评委系统数据库迁移脚本
-- Supabase Project: AI-Judge-System (tkcryitcxidskbqcihnt)

-- ============================================================
-- 1. profiles 表（用户扩展信息）
-- ============================================================
CREATE TABLE profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own profile" ON profiles
  FOR SELECT USING ((select auth.uid()) = id);
CREATE POLICY "Users can update own profile" ON profiles
  FOR UPDATE USING ((select auth.uid()) = id);
CREATE POLICY "Users can insert own profile" ON profiles
  FOR INSERT WITH CHECK ((select auth.uid()) = id);

-- ============================================================
-- 2. projects 表（参赛项目）
-- ============================================================
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  competition TEXT NOT NULL,
  track TEXT NOT NULL,
  "group" TEXT NOT NULL,
  current_stage TEXT DEFAULT 'school_text',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_projects_user ON projects(user_id);

ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own projects" ON projects
  FOR SELECT USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can create own projects" ON projects
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);
CREATE POLICY "Users can update own projects" ON projects
  FOR UPDATE USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can delete own projects" ON projects
  FOR DELETE USING ((select auth.uid()) = user_id);

-- ============================================================
-- 3. project_materials 表（项目材料）
-- ============================================================
CREATE TABLE project_materials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  material_type TEXT NOT NULL,
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  file_size BIGINT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1,
  image_paths JSONB,
  is_latest BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_materials_project_type ON project_materials(project_id, material_type, is_latest);

ALTER TABLE project_materials ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own project materials" ON project_materials
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_materials.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can insert own project materials" ON project_materials
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_materials.project_id AND projects.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can update own project materials" ON project_materials
  FOR UPDATE USING (
    EXISTS (SELECT 1 FROM projects WHERE projects.id = project_materials.project_id AND projects.user_id = (select auth.uid()))
  );

-- ============================================================
-- 4. reviews 表（评审记录）
-- ============================================================
CREATE TABLE reviews (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id),
  review_type TEXT NOT NULL,
  competition TEXT NOT NULL,
  track TEXT NOT NULL,
  "group" TEXT NOT NULL,
  stage TEXT NOT NULL,
  judge_style TEXT DEFAULT 'strict',
  total_score NUMERIC(5,2),
  material_versions JSONB,
  status TEXT DEFAULT 'pending',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE INDEX idx_reviews_project ON reviews(project_id, created_at DESC);
CREATE INDEX idx_reviews_user ON reviews(user_id);

ALTER TABLE reviews ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own reviews" ON reviews
  FOR SELECT USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can create own reviews" ON reviews
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);
CREATE POLICY "Users can update own reviews" ON reviews
  FOR UPDATE USING ((select auth.uid()) = user_id);

-- ============================================================
-- 5. review_details 表（评审维度详情）
-- ============================================================
CREATE TABLE review_details (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id UUID NOT NULL REFERENCES reviews(id) ON DELETE CASCADE,
  dimension TEXT NOT NULL,
  max_score NUMERIC(5,2) NOT NULL,
  score NUMERIC(5,2) NOT NULL,
  sub_items JSONB,
  suggestions JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_review_details_review ON review_details(review_id);

ALTER TABLE review_details ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own review details" ON review_details
  FOR SELECT USING (
    EXISTS (SELECT 1 FROM reviews WHERE reviews.id = review_details.review_id AND reviews.user_id = (select auth.uid()))
  );
CREATE POLICY "Users can insert own review details" ON review_details
  FOR INSERT WITH CHECK (
    EXISTS (SELECT 1 FROM reviews WHERE reviews.id = review_details.review_id AND reviews.user_id = (select auth.uid()))
  );

-- ============================================================
-- 6. custom_voices 表（自定义音色）
-- ============================================================
CREATE TABLE custom_voices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  voice TEXT NOT NULL,
  preferred_name TEXT NOT NULL,
  target_model TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_custom_voices_user ON custom_voices(user_id);

ALTER TABLE custom_voices ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own custom voices" ON custom_voices
  FOR SELECT USING ((select auth.uid()) = user_id);
CREATE POLICY "Users can create own custom voices" ON custom_voices
  FOR INSERT WITH CHECK ((select auth.uid()) = user_id);
CREATE POLICY "Users can delete own custom voices" ON custom_voices
  FOR DELETE USING ((select auth.uid()) = user_id);
