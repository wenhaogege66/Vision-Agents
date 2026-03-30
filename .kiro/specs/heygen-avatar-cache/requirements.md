# 需求文档：HeyGen Avatar 与 Voice 缓存机制

## 简介

当前系统每次用户打开数字人问辩页面时，都会实时调用 HeyGen API 获取全量 avatar 和 voice 数据。HeyGen 的 `/v2/avatars` 接口返回内容多且不支持分页，导致页面加载缓慢。本功能在后端引入缓存机制，将 HeyGen 的 avatar 和 voice 数据同步到本地 Supabase PostgreSQL 数据库，前端改为从后端缓存读取并支持分页，从而大幅提升页面加载速度。

## 术语表

- **Cache_Sync_Service**：后端缓存同步服务，负责从 HeyGen API 拉取 avatar 和 voice 数据并写入本地数据库
- **Avatar_Cache_Table**：存储 avatar 缓存数据的数据库表（`heygen_avatar_cache`）
- **Voice_Cache_Table**：存储 voice 缓存数据的数据库表（`heygen_voice_cache`）
- **Sync_Metadata_Table**：存储同步元数据的数据库表（`heygen_sync_metadata`），记录最近一次同步时间和状态
- **Cache_API**：后端提供给前端的缓存数据查询 API，支持分页和搜索
- **HeyGen_API**：HeyGen 官方 REST API，包括 `/v2/avatars`、`/v2/avatar_group.list`、`/v2/avatar_group/{id}/avatars`、`/v2/voices`
- **Scheduler**：后端定时任务调度器，负责每日自动触发缓存同步

## 需求

### 需求 1：数据库缓存表设计

**用户故事：** 作为系统管理员，我希望 avatar 和 voice 数据存储在本地数据库中，以便前端能快速查询并支持分页和搜索。

#### 验收标准

1. THE Avatar_Cache_Table SHALL 包含以下字段：id（主键）、heygen_avatar_id（HeyGen 原始 ID）、name、preview_image_url、avatar_type（photo_avatar / digital_twin）、is_custom（用户自有 vs 公共）、group_id（所属 avatar group ID，可为空）、status、default_voice_id（可为空）、synced_at（同步时间戳）、created_at、updated_at
2. THE Voice_Cache_Table SHALL 包含以下字段：id（主键）、heygen_voice_id（HeyGen 原始 ID）、name、language、gender、preview_audio（预览音频 URL）、is_custom（用户自有 vs 公共）、synced_at（同步时间戳）、created_at、updated_at
3. THE Sync_Metadata_Table SHALL 包含以下字段：id（主键）、resource_type（avatar / voice）、last_sync_at（最近同步完成时间）、last_sync_status（success / failed）、last_sync_error（错误信息，可为空）、avatar_count（同步的 avatar 数量）、voice_count（同步的 voice 数量）
4. THE Avatar_Cache_Table SHALL 在 name 字段上创建索引以支持按名称搜索
5. THE Avatar_Cache_Table SHALL 在 heygen_avatar_id 字段上创建唯一索引以防止重复数据
6. THE Voice_Cache_Table SHALL 在 heygen_voice_id 字段上创建唯一索引以防止重复数据

### 需求 2：后端缓存同步服务

**用户故事：** 作为系统管理员，我希望后端能自动从 HeyGen API 同步 avatar 和 voice 数据到本地数据库，以便缓存数据保持最新。

#### 验收标准

1. WHEN 后端应用启动时，THE Cache_Sync_Service SHALL 检查 Sync_Metadata_Table 中最近一次同步时间（last_sync_at），仅当距离当前时间超过 24 小时或从未同步过时，才异步执行一次全量同步
2. WHEN 全量同步执行时，THE Cache_Sync_Service SHALL 依次调用 HeyGen_API 的 avatar_group.list、avatar_group/{id}/avatars 和 /v2/avatars 接口获取所有 avatar 数据
3. WHEN 全量同步执行时，THE Cache_Sync_Service SHALL 调用 HeyGen_API 的 /v2/voices 接口获取所有 voice 数据
4. WHEN 同步数据写入数据库时，THE Cache_Sync_Service SHALL 使用 upsert 策略（基于 heygen_avatar_id / heygen_voice_id），对已存在的记录更新字段，对新记录执行插入
5. WHEN 同步完成后，THE Cache_Sync_Service SHALL 删除数据库中存在但 HeyGen API 返回中不存在的记录，以保持数据一致性
6. WHEN 同步成功完成时，THE Cache_Sync_Service SHALL 更新 Sync_Metadata_Table 中对应 resource_type 的 last_sync_at 为当前时间、last_sync_status 为 success、avatar_count 和 voice_count 为实际同步数量
7. IF HeyGen_API 调用失败或超时，THEN THE Cache_Sync_Service SHALL 记录错误日志，更新 Sync_Metadata_Table 的 last_sync_status 为 failed 和 last_sync_error 为错误信息，并保留现有缓存数据不变
8. THE Cache_Sync_Service SHALL 在同步过程中不阻塞 API 请求处理

### 需求 3：定时自动同步

**用户故事：** 作为系统管理员，我希望缓存数据每天自动更新一次，以便用户在 HeyGen 官网新增的 avatar 能在次日自动出现在系统中。

#### 验收标准

1. THE Scheduler SHALL 每 24 小时自动触发一次 Cache_Sync_Service 的全量同步
2. WHEN 定时同步任务执行时，THE Scheduler SHALL 以异步方式运行，不阻塞正在处理的 API 请求
3. IF 定时同步任务执行失败，THEN THE Scheduler SHALL 记录错误日志并在下一个周期继续尝试

### 需求 4：手动触发同步 API

**用户故事：** 作为用户，我希望在 HeyGen 官网创建新 avatar 后能手动触发同步，以便立即在系统中看到新创建的 avatar。

#### 验收标准

1. WHEN 收到 POST 请求到手动同步端点时，THE Cache_API SHALL 触发 Cache_Sync_Service 执行一次全量同步
2. WHEN 手动同步被触发时，THE Cache_API SHALL 立即返回 202 Accepted 响应，包含同步任务状态信息，不等待同步完成
3. IF 已有同步任务正在执行中，THEN THE Cache_API SHALL 返回 409 Conflict 响应，提示用户等待当前同步完成
4. THE Cache_API SHALL 提供 GET 端点查询最近一次同步的状态信息（last_sync_at、last_sync_status、avatar_count、voice_count）

### 需求 5：前端分页查询 API

**用户故事：** 作为用户，我希望从后端缓存中分页加载 avatar 和 voice 列表，以便页面加载速度更快。

#### 验收标准

1. WHEN 收到 GET 请求查询 avatar 列表时，THE Cache_API SHALL 从 Avatar_Cache_Table 读取数据并返回分页结果
2. WHEN 收到 GET 请求查询 voice 列表时，THE Cache_API SHALL 从 Voice_Cache_Table 读取数据并返回分页结果
3. THE Cache_API SHALL 支持以下分页参数：page（页码，默认 1）、page_size（每页数量，默认 20）
4. THE Cache_API SHALL 在响应中包含分页元数据：total（总记录数）、page（当前页码）、page_size（每页数量）、total_pages（总页数）
5. WHEN 请求包含 search 参数时，THE Cache_API SHALL 对 name 字段执行模糊匹配过滤
6. WHEN 请求 avatar 列表包含 is_custom 参数时，THE Cache_API SHALL 按 is_custom 字段过滤结果
7. THE Cache_API SHALL 返回的 avatar 数据格式与当前前端 AvatarInfo 类型兼容（id、name、preview_image_url、avatar_type、is_custom）
8. IF Avatar_Cache_Table 为空（尚未完成首次同步），THEN THE Cache_API SHALL 返回空列表和 total 为 0 的分页元数据

### 需求 6：前端适配缓存 API

**用户故事：** 作为用户，我希望数字人问辩页面使用缓存数据加载 avatar 和 voice 列表，以便页面加载更快且支持分页浏览。

#### 验收标准

1. WHEN 数字人问辩页面加载时，THE 前端 SHALL 调用新的缓存分页 API 替代原有的直接 HeyGen API 调用
2. THE 前端 SHALL 在 avatar 选择器中实现分页加载，支持滚动加载更多或分页切换
3. THE 前端 SHALL 在 avatar 选择器中保留"我的"和"公共"分组显示逻辑
4. WHEN 用户点击手动刷新按钮时，THE 前端 SHALL 调用手动同步 API 并在同步完成后刷新 avatar 和 voice 列表
5. THE 前端 SHALL 在 voice 选择器中使用缓存 API 加载 voice 列表
