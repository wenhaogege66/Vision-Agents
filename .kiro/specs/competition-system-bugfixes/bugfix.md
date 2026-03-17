# 缺陷修复需求文档

## 简介

AI评委系统存在四个缺陷：（1）材料相关 API 返回 500 错误，原因是后端使用 publishable key（anon key）初始化的共享 Supabase 客户端查询启用了 RLS 的 `project_materials` 表，但未携带用户 JWT，导致 `auth.uid()` 为 NULL，RLS 策略拒绝访问；（2）前端页面刷新时 API 被重复调用两次，原因是 React StrictMode 在开发模式下会双重执行 useEffect；（3）材料上传失败，原因是 Supabase Storage 中 `materials` bucket 未创建（已通过 Supabase MCP 修复），且上传操作同样受 RLS 限制需要正确的 auth 上下文。

---

## 缺陷分析

### 根因诊断

通过 Supabase MCP Power 检查发现：
- 后端 `.env` 中 `SUPABASE_KEY` 使用的是 `sb_publishable_` 开头的 publishable key（等同于 anon key），受 RLS 策略限制
- `storage.buckets` 表中无 `materials` bucket（已通过 MCP 创建并配置 Storage RLS 策略）
- 所有 `project_materials` 表的 RLS 策略均依赖 `auth.uid()`，而后端共享客户端未设置用户 JWT，导致 `auth.uid()` 为 NULL
- `profiles` 表同样受 RLS 保护，后端查询 profile 时也会因 `auth.uid()` 为 NULL 而失败（终端提示"查询 profile 失败，display_name 将为空"）

### 当前行为（缺陷）

1.1 WHEN 用户创建项目后进入项目详情页，后端通过共享 Supabase 客户端（publishable key，未设置用户 JWT）查询 `project_materials` 表 THEN 系统返回 500 Internal Server Error，因为 RLS 策略中 `auth.uid()` 为 NULL 导致查询被拒绝

1.2 WHEN 用户首次点击"材料中心"页面，后端通过共享 Supabase 客户端查询 `project_materials` 表获取材料列表 THEN 系统返回两个 500 错误（`GET /api/projects/{project_id}/materials` 被调用两次均失败）

1.3 WHEN 用户在 `/projects` 页面刷新，或进入具体项目页面 THEN `/api/auth/me`、`/api/projects`、`/api/projects/{id}` 等接口各被调用两次，造成不必要的重复请求

1.4 WHEN 用户上传材料文件时，后端尝试将文件上传到 Supabase Storage 的 `materials` bucket THEN 上传失败，因为（a）bucket 之前不存在（已修复），（b）Storage 操作同样需要正确的 auth 上下文才能通过 RLS 策略，（c）文件名包含中文字符时 Supabase Storage 返回 `InvalidKey` 错误（Storage path 不支持非 ASCII 字符）

1.5 WHEN 后端在任何请求中查询 `profiles` 表获取 `display_name` THEN 查询静默失败（终端提示"查询 profile 失败，display_name 将为空"），因为 `profiles` 表 RLS 策略要求 `auth.uid() = id`，而共享客户端未设置用户 JWT

### 预期行为（正确）

2.1 WHEN 用户进入项目详情页，后端查询 `project_materials` 表获取材料状态 THEN 系统 SHALL 成功返回材料状态数据（后端应使用 service_role key 创建 Supabase 客户端以绕过 RLS，因为后端已在应用层通过 `get_current_user` 做了权限校验）

2.2 WHEN 用户点击"材料中心"页面，后端查询 `project_materials` 表获取材料列表 THEN 系统 SHALL 成功返回材料列表数据，不出现 500 错误

2.3 WHEN 用户在前端页面刷新或导航时 THEN 系统 SHALL 每个 API 请求只发送一次，避免重复调用（通过移除 StrictMode 或使用 useEffect cleanup / 请求去重机制）

2.4 WHEN 用户上传材料文件 THEN 系统 SHALL 成功将文件上传到 Storage 并插入 `project_materials` 记录

2.5 WHEN 后端查询 `profiles` 表获取用户 `display_name` THEN 系统 SHALL 成功返回 display_name 数据

### 修复方案

核心修复：将后端 `SUPABASE_KEY` 从 publishable key / secret key 改为 legacy service_role key（JWT 格式，`eyJ...` 开头）。新的 publishable/secret key 体系与 `supabase-py` SDK 不兼容，SDK 期望 JWT 格式的 key。后端作为可信服务端，已通过 `get_current_user` 依赖项在应用层验证用户身份和权限，因此可以安全地使用 service_role key 绕过 RLS。这将一次性解决 Bug 1.1、1.2、1.4、1.5。

Storage 文件名修复：将 Storage path 中的原始文件名替换为 UUID + 扩展名的格式（如 `v1_a3b2c1d4.pdf`），避免中文文件名导致 Supabase Storage 返回 `InvalidKey` 错误。原始文件名仍保存在 `project_materials` 表的 `file_name` 字段中。（已在代码中修复）

Supabase 配置修复：通过 Supabase MCP 创建了 `materials` Storage bucket 并配置了对应的 RLS 策略。（已完成）

前端修复：移除 React StrictMode 以消除开发模式下的重复 API 调用（Bug 1.3）。

### 不变行为（回归防护）

3.1 WHEN 用户通过正常认证流程登录后访问 `projects` 表的 CRUD 操作 THEN 系统 SHALL 继续正常返回项目数据，后端应用层权限校验不受影响

3.2 WHEN 用户上传材料文件（POST `/api/projects/{project_id}/materials`）THEN 系统 SHALL 正常上传文件到 Storage 并插入 `project_materials` 记录

3.3 WHEN 用户执行登录、注册、获取用户信息等认证操作 THEN 系统 SHALL 继续正常工作，认证流程不受影响

3.4 WHEN 用户访问评审、路演等其他功能模块 THEN 系统 SHALL 继续正常工作，不受本次修复影响

3.5 WHEN 未认证用户尝试访问受保护的 API 端点 THEN 系统 SHALL 继续返回 401 错误，应用层安全不受影响
