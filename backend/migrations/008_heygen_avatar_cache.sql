-- HeyGen Avatar/Voice 缓存机制 - 数据库迁移脚本
-- 变更: 新增 heygen_avatar_cache、heygen_voice_cache、heygen_sync_metadata 三张缓存表
-- 需求: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6

-- ============================================================
-- 1. heygen_avatar_cache: 缓存 HeyGen avatar 数据
-- ============================================================

CREATE TABLE IF NOT EXISTS heygen_avatar_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heygen_avatar_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    preview_image_url TEXT NOT NULL DEFAULT '',
    avatar_type TEXT NOT NULL DEFAULT 'photo_avatar'
        CHECK (avatar_type IN ('photo_avatar', 'digital_twin')),
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    group_id TEXT,
    status TEXT DEFAULT 'active',
    default_voice_id TEXT,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_heygen_avatar_id UNIQUE (heygen_avatar_id)
);

CREATE INDEX IF NOT EXISTS idx_hac_name ON heygen_avatar_cache (name);
CREATE INDEX IF NOT EXISTS idx_hac_is_custom ON heygen_avatar_cache (is_custom);

-- ============================================================
-- 2. heygen_voice_cache: 缓存 HeyGen voice 数据
-- ============================================================

CREATE TABLE IF NOT EXISTS heygen_voice_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    heygen_voice_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    language TEXT NOT NULL DEFAULT '',
    gender TEXT NOT NULL DEFAULT '',
    preview_audio TEXT NOT NULL DEFAULT '',
    is_custom BOOLEAN NOT NULL DEFAULT FALSE,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_heygen_voice_id UNIQUE (heygen_voice_id)
);

CREATE INDEX IF NOT EXISTS idx_hvc_name ON heygen_voice_cache (name);

-- ============================================================
-- 3. heygen_sync_metadata: 同步元数据
-- ============================================================

CREATE TABLE IF NOT EXISTS heygen_sync_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_type TEXT NOT NULL UNIQUE CHECK (resource_type IN ('avatar', 'voice')),
    last_sync_at TIMESTAMPTZ,
    last_sync_status TEXT DEFAULT 'never'
        CHECK (last_sync_status IN ('never', 'success', 'failed')),
    last_sync_error TEXT,
    avatar_count INT DEFAULT 0,
    voice_count INT DEFAULT 0
);

-- 预插入元数据行
INSERT INTO heygen_sync_metadata (resource_type, last_sync_status)
VALUES ('avatar', 'never'), ('voice', 'never')
ON CONFLICT (resource_type) DO NOTHING;

-- ============================================================
-- 4. RLS 策略：缓存表对已认证用户只读，service_role 可写
-- ============================================================

ALTER TABLE heygen_avatar_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE heygen_voice_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE heygen_sync_metadata ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_read_avatar_cache" ON heygen_avatar_cache
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated_read_voice_cache" ON heygen_voice_cache
    FOR SELECT TO authenticated USING (true);

CREATE POLICY "authenticated_read_sync_metadata" ON heygen_sync_metadata
    FOR SELECT TO authenticated USING (true);

-- service_role 可以写入（后端使用 service_role key）
CREATE POLICY "service_write_avatar_cache" ON heygen_avatar_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_write_voice_cache" ON heygen_voice_cache
    FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_write_sync_metadata" ON heygen_sync_metadata
    FOR ALL TO service_role USING (true) WITH CHECK (true);
