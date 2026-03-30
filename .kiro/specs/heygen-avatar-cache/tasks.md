# 实施计划：HeyGen Avatar 与 Voice 缓存机制

## 概述

将 HeyGen avatar/voice 数据从实时 API 调用迁移到本地数据库缓存模式。后端使用 FastAPI + Python 3.13 + Supabase PostgreSQL，前端使用 React + TypeScript。按照数据库 → 模型 → 服务 → 调度 → 路由 → 前端的顺序递增实现。

## Tasks

- [x] 1. 创建数据库迁移脚本
  - [x] 1.1 创建 `backend/migrations/008_heygen_avatar_cache.sql`
    - 创建 `heygen_avatar_cache` 表，包含 id、heygen_avatar_id（UNIQUE）、name、preview_image_url、avatar_type（CHECK 约束）、is_custom、group_id、status、default_voice_id、synced_at、created_at、updated_at
    - 创建 `heygen_voice_cache` 表，包含 id、heygen_voice_id（UNIQUE）、name、language、gender、preview_audio、is_custom、synced_at、created_at、updated_at
    - 创建 `heygen_sync_metadata` 表，包含 id、resource_type（UNIQUE + CHECK）、last_sync_at、last_sync_status、last_sync_error、avatar_count、voice_count
    - 创建索引：idx_hac_name、idx_hac_is_custom、idx_hvc_name
    - 预插入 avatar 和 voice 两行元数据
    - 启用 RLS 策略：authenticated 只读 + service_role 可写
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 2. 新增 Pydantic 模型和后端缓存同步服务
  - [x] 2.1 在 `backend/app/models/schemas.py` 中新增缓存相关 Pydantic 模型
    - 新增 `AvatarCacheItem`、`VoiceCacheItem`、`PaginatedResponse`、`SyncStatusResponse` 四个模型
    - _Requirements: 5.4, 5.7_

  - [x] 2.2 创建 `backend/app/services/avatar/cache_sync_service.py` 实现 CacheSyncService
    - 实现 `__init__`（接收 supabase Client，初始化 asyncio.Lock）
    - 实现 `maybe_sync()`：查询 sync_metadata，判断是否需要同步（>24h 或从未同步）
    - 实现 `force_sync()`：获取锁后执行全量同步，锁被占用时抛出异常
    - 实现 `_do_full_sync()`：调用 _sync_avatars + _sync_voices → upsert → cleanup → update metadata
    - 实现 `_sync_avatars()`：调用 HeyGen avatar_group.list + avatar_group/{id}/avatars + /v2/avatars
    - 实现 `_sync_voices()`：调用 HeyGen /v2/voices
    - 实现 `_upsert_avatars()` 和 `_upsert_voices()`：批量 upsert 到缓存表
    - 实现 `_cleanup_stale()`：删除不在最新批次中的记录
    - 实现 `_update_metadata()`：更新 sync_metadata 表
    - 实现 `get_sync_status()` 和 `is_syncing()`
    - HeyGen API 失败时保留现有缓存不变，更新 metadata 为 failed
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8_

  - [ ]* 2.3 写属性测试：Upsert 幂等性
    - **Property 1: Upsert 幂等性**
    - 生成随机 avatar/voice 数据，对同一 heygen_avatar_id 执行两次 upsert，验证记录唯一且值等于最后一次输入
    - **Validates: Requirements 1.5, 1.6, 2.4**

  - [ ]* 2.4 写属性测试：同步决策正确性
    - **Property 2: 同步决策正确性**
    - 生成随机 last_sync_at 时间戳（或 None），验证 maybe_sync 仅在 >24h 或 None 时执行同步
    - **Validates: Requirements 2.1**

  - [ ]* 2.5 写属性测试：过期数据清理
    - **Property 4: 过期数据清理**
    - 生成随机旧缓存集合和新批次集合，验证清理后缓存恰好等于新批次
    - **Validates: Requirements 2.5**

  - [ ]* 2.6 写属性测试：同步元数据一致性
    - **Property 5: 同步元数据一致性**
    - 同步 N 个 avatar 和 M 个 voice 后，验证 metadata 中 status=success、count 正确、last_sync_at 不早于同步开始时间
    - **Validates: Requirements 2.6**

  - [ ]* 2.7 写属性测试：失败时缓存不变性
    - **Property 6: 失败时缓存不变性**
    - 模拟 HeyGen API 失败，验证缓存数据与失败前完全一致，metadata status=failed
    - **Validates: Requirements 2.7**

  - [ ]* 2.8 写属性测试：并发同步互斥
    - **Property 7: 并发同步互斥**
    - 模拟正在执行同步时再次请求同步，验证被拒绝（409）且不启动第二个同步任务
    - **Validates: Requirements 4.3**

- [ ] 3. Checkpoint - 确保后端服务层代码无语法错误
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 集成调度器和缓存查询路由
  - [x] 4.1 在 `backend/app/main.py` 中集成缓存同步调度
    - 在 startup 事件中添加 `CacheSyncService.maybe_sync()` 异步任务
    - 添加 `_periodic_cache_sync()` 后台循环（每 24h 执行 force_sync）
    - 在 shutdown 事件中清理调度任务
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.2 在 `backend/app/routes/defense.py` 中新增缓存查询路由
    - `GET /avatar/cache/avatars`：分页查询 avatar 缓存，支持 page、page_size、search、is_custom 参数
    - `GET /avatar/cache/voices`：分页查询 voice 缓存，支持 page、page_size、search 参数
    - `POST /avatar/cache/sync`：手动触发同步，返回 202；锁被占用返回 409
    - `GET /avatar/cache/sync-status`：查询同步状态
    - 分页逻辑：计算 total、total_pages、offset，返回 PaginatedResponse
    - 搜索逻辑：name 字段 ILIKE 模糊匹配
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 4.3 写属性测试：分页正确性
    - **Property 8: 分页正确性**
    - 生成随机记录数和分页参数，验证 items 数量、total、total_pages 计算正确
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

  - [ ]* 4.4 写属性测试：搜索过滤正确性
    - **Property 9: 搜索过滤正确性**
    - 生成随机名称和搜索词，验证返回的每条记录 name 包含搜索词（不区分大小写），且所有匹配记录都被返回
    - **Validates: Requirements 5.5**

  - [ ]* 4.5 写属性测试：is_custom 过滤正确性
    - **Property 10: is_custom 过滤正确性**
    - 生成随机 is_custom 值的记录，验证过滤后每条记录的 is_custom 等于过滤值
    - **Validates: Requirements 5.6**

- [ ] 5. Checkpoint - 确保后端所有路由和调度器正常工作
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 前端适配缓存 API
  - [x] 6.1 在 `frontend/src/types/index.ts` 中新增缓存相关类型
    - 新增 `AvatarCacheItem`、`VoiceCacheItem`、`PaginatedResponse<T>`、`SyncStatusResponse`、`CacheQueryParams` 类型定义
    - _Requirements: 5.7_

  - [x] 6.2 在 `frontend/src/services/api.ts` 中新增缓存 API 方法
    - `defenseApi` 新增 `listCachedAvatars(projectId, params)`：GET `/cache/avatars`
    - `defenseApi` 新增 `listCachedVoices(projectId, params)`：GET `/cache/voices`
    - `defenseApi` 新增 `triggerCacheSync(projectId)`：POST `/cache/sync`
    - `defenseApi` 新增 `getCacheSyncStatus(projectId)`：GET `/cache/sync-status`
    - _Requirements: 6.1, 6.5_

  - [x] 6.3 修改 `frontend/src/pages/DigitalDefense.tsx` 使用缓存 API
    - 将 `defenseApi.listHeygenAvatars` 替换为 `defenseApi.listCachedAvatars`，支持分页参数
    - 将 `defenseApi.listHeygenVoices` 替换为 `defenseApi.listCachedVoices`
    - Avatar Select 组件添加 `onPopupScroll` 实现滚动加载更多
    - 保留"我的"和"公共"分组显示逻辑（基于 is_custom 字段）
    - 新增"刷新缓存"按钮，调用 `triggerCacheSync` 并在完成后刷新列表
    - Voice Select 同样改为缓存 API
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 7. 最终 Checkpoint - 确保前后端联调正常
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 后端语言：Python 3.13 + FastAPI，前端语言：TypeScript + React
- 数据库迁移编号为 008，紧接现有的 007_heygen_mode_optimization.sql
- 属性测试使用 Hypothesis 库，测试文件位于 `backend/tests/test_heygen_avatar_cache.py`
- CacheSyncService 使用 asyncio.Lock 实现并发互斥，不引入外部调度依赖
- 同步服务复用 `HeyGenVideoService` 中已有的 HeyGen API URL 常量
