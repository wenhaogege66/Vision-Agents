# Implementation Plan: 数字人问辩 (Digital Human Defense)

## Overview

基于需求和设计文档，按依赖顺序实现数字人问辩功能。从数据库迁移和后端配置开始，逐步构建后端服务、路由，再到前端类型、API 封装、组件和页面，最后集成问题自动生成和波形可视化。

## Tasks

- [x] 1. 数据库迁移与后端配置
  - [x] 1.1 创建数据库迁移文件 `backend/migrations/004_digital_human_defense.sql`
    - 创建 `defense_questions` 表（id, project_id, content, sort_order, created_at, updated_at）
    - 创建 `defense_records` 表（id, project_id, user_id, questions_snapshot, user_answer_text, ai_feedback_text, answer_duration, status, created_at）
    - 为 `defense_questions` 和 `defense_records` 启用 RLS 行级安全策略
    - 为 `project_id` 字段创建索引
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 1.2 在 `backend/app/config.py` 中新增 HeyGen 配置项
    - 添加 `heygen_api_key: str = ""` 和 `heygen_avatar_id: str = "80d4afa941c243beb0a1116c95ea48ee"`
    - 更新 `backend/.env.example` 添加 `HEYGEN_API_KEY` 和 `HEYGEN_AVATAR_ID` 示例
    - _Requirements: 11.1, 11.2_

- [x] 2. 后端 Pydantic 模型与服务层
  - [x] 2.1 在 `backend/app/models/schemas.py` 中新增数字人问辩相关模型
    - 添加 `DefenseQuestionCreate`、`DefenseQuestionResponse`、`DefenseRecordResponse` 模型
    - `DefenseQuestionCreate.content` 需包含长度校验（非空且 <= 40 字）
    - _Requirements: 2.5, 2.6, 10.1, 10.2_

  - [x] 2.2 创建 `backend/app/services/heygen_service.py`
    - 实现 `HeyGenService.create_token()` 方法，调用 HeyGen API 生成 streaming access token
    - 处理 `HEYGEN_API_KEY` 未配置的情况（记录警告日志，返回 503 错误）
    - 处理 HeyGen API 调用失败的情况（返回 502 错误）
    - _Requirements: 11.3, 11.4, 4.1_

  - [x] 2.3 创建 `backend/app/services/defense_service.py`
    - 实现 `DefenseService` 类，包含问题 CRUD 方法：`list_questions`、`create_question`、`update_question`、`delete_question`
    - 实现 `generate_questions` 方法：基于 project_profile 调用通义千问 AI 生成 3 个评委问题，每个问题 <= 40 字
    - 实现 `submit_answer` 方法：接收音频 → 调用 Deepgram STT 转写 → 加载项目上下文 → 调用通义千问生成 20-60 字反馈 → 存储 defense_record
    - 实现 `list_records` 方法：按 created_at 倒序返回问辩记录
    - 实现 `format_questions_speech` 辅助函数：将问题列表组合为自然语言提问文本
    - 实现 `clamp_duration` 辅助函数：将回答时长钳制到 [10, 120] 范围
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.2, 2.3, 2.4, 5.5, 5.6, 6.5, 7.1, 7.2, 7.3, 7.4, 8.1, 8.2, 9.2, 9.4_

  - [ ]* 2.4 编写 `format_questions_speech` 属性测试
    - **Property 6: 问题组合文本格式正确**
    - **Validates: Requirements 5.5, 5.6**

  - [ ]* 2.5 编写 `clamp_duration` 属性测试
    - **Property 10: 回答时长范围钳制**
    - **Validates: Requirements 9.2, 9.4**

  - [ ]* 2.6 编写问题内容校验属性测试
    - **Property 5: 问题内容校验拒绝无效输入**
    - **Validates: Requirements 2.5, 2.6**

- [x] 3. Checkpoint - 确保后端模型和服务层代码无语法错误
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. 后端路由与项目简介集成
  - [x] 4.1 创建 `backend/app/routes/defense.py`
    - 实现 `POST /api/projects/{project_id}/defense/token` — 获取 HeyGen access token
    - 实现 `GET /api/projects/{project_id}/defense/questions` — 获取问题列表
    - 实现 `POST /api/projects/{project_id}/defense/questions` — 创建问题
    - 实现 `PUT /api/projects/{project_id}/defense/questions/{question_id}` — 更新问题
    - 实现 `DELETE /api/projects/{project_id}/defense/questions/{question_id}` — 删除问题（返回 204）
    - 实现 `POST /api/projects/{project_id}/defense/submit-answer` — 提交回答音频，返回 DefenseRecord
    - 实现 `GET /api/projects/{project_id}/defense/records` — 获取问辩记录列表
    - 所有端点需要 `get_current_user` 认证依赖
    - _Requirements: 2.1-2.6, 6.5, 7.1-7.6, 8.1-8.5, 11.3_

  - [x] 4.2 在 `backend/app/main.py` 中注册 defense 路由
    - 导入并注册 defense router
    - _Requirements: 4.1_

  - [x] 4.3 修改 `backend/app/services/profile_service.py` 的 `extract_profile` 方法
    - 在项目简介提取完成后，调用 `DefenseService.generate_questions` 自动生成 3 个评委问题
    - 生成失败不影响简介提取的正常返回（捕获异常并记录日志）
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 4.4 编写 AI 生成问题长度约束属性测试
    - **Property 1: AI 生成的问题长度约束**
    - **Validates: Requirements 1.2, 1.4**

  - [ ]* 4.5 编写 AI 反馈长度约束属性测试
    - **Property 11: AI 反馈长度约束**
    - **Validates: Requirements 7.2, 7.3**

- [x] 5. Checkpoint - 确保后端路由和集成代码完整
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. 前端类型定义与 API 封装
  - [x] 6.1 在 `frontend/src/types/index.ts` 中新增数字人问辩类型
    - 添加 `DefenseQuestion` 和 `DefenseRecord` 接口定义
    - _Requirements: 10.1, 10.2_

  - [x] 6.2 在 `frontend/src/services/api.ts` 中新增 `defenseApi` 封装
    - 实现 `getToken`、`listQuestions`、`createQuestion`、`updateQuestion`、`deleteQuestion`、`submitAnswer`、`listRecords` 方法
    - `submitAnswer` 使用 `multipart/form-data` 上传音频，设置 120s 超时
    - _Requirements: 2.1-2.6, 6.5, 7.1, 8.1_

- [x] 7. 前端组件：预定义问题管理
  - [x] 7.1 创建 `frontend/src/components/DefenseQuestionManager.tsx`
    - 显示预定义问题列表，支持新增、编辑、删除操作
    - 40 字限制前端校验，空内容校验
    - 使用 Ant Design 组件（List、Input、Button、Popconfirm）
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 7.2 将 `DefenseQuestionManager` 嵌入 `frontend/src/pages/ProjectDashboard.tsx`
    - 在项目简介区域下方显示问题管理组件
    - _Requirements: 2.1_

- [x] 8. 前端组件：语音波形可视化
  - [x] 8.1 创建 `frontend/src/components/AudioWaveform.tsx`
    - 使用 Web Audio API 的 AnalyserNode 实现实时音频波形可视化
    - 接收 MediaStream 作为输入，使用 Canvas 绘制动态波形
    - _Requirements: 6.2_

- [x] 9. 前端页面：数字人问辩
  - [x] 9.1 安装 `@heygen/streaming-avatar` npm 依赖
    - 在 `frontend/` 目录下执行 `npm install @heygen/streaming-avatar`
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 9.2 创建 `frontend/src/pages/DigitalDefense.tsx`
    - 实现问辩页面完整 UI 和状态机（idle → loading → speaking → recording → processing → feedback → done）
    - 集成 HeyGen Streaming Avatar SDK：创建 session、speak、stopAvatar
    - 实现 MediaRecorder 录音功能，集成 AudioWaveform 波形可视化
    - 实现倒计时显示（使用用户设置的 answer_duration）
    - 显示历史问辩记录列表（按时间倒序）
    - 提供 answer_duration 输入框（默认 30 秒，范围 10-120 秒）
    - 处理 Avatar Session 创建失败、断开重连、麦克风权限等错误场景
    - 页面卸载时自动关闭 Avatar Session（useEffect cleanup + beforeunload）
    - _Requirements: 3.1-3.7, 4.1-4.7, 5.1-5.6, 6.1-6.8, 7.5, 7.6, 8.2-8.5, 9.1-9.4_

  - [x] 9.3 在 `frontend/src/App.tsx` 中注册数字人问辩路由
    - 添加 `/projects/:projectId/defense` 路由指向 `DigitalDefense` 页面
    - _Requirements: 3.1_

  - [x] 9.4 在 `frontend/src/pages/ProjectDashboard.tsx` 中添加"数字人问辩"功能卡片
    - 在快捷操作区域添加功能卡片，与"文本评审"、"离线评审"等并列
    - 当预定义问题数量为 0 时禁用卡片并显示提示
    - 当预定义问题数量 >= 1 时启用卡片，点击跳转到问辩页面
    - _Requirements: 3.1, 3.2, 3.3_

- [x] 10. Checkpoint - 确保前后端集成完整
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. 属性测试与单元测试
  - [ ]* 11.1 编写问题创建 round-trip 属性测试
    - **Property 2: 问题创建 round-trip**
    - **Validates: Requirements 2.2, 1.5**

  - [ ]* 11.2 编写问题更新保持内容一致属性测试
    - **Property 3: 问题更新保持内容一致**
    - **Validates: Requirements 2.3**

  - [ ]* 11.3 编写问题删除后不可查询属性测试
    - **Property 4: 问题删除后不可查询**
    - **Validates: Requirements 2.4**

  - [ ]* 11.4 编写问辩记录持久化完整性属性测试
    - **Property 7: 问辩记录持久化完整性**
    - **Validates: Requirements 6.8, 7.4, 8.1, 9.3**

  - [ ]* 11.5 编写历史记录按时间倒序排列属性测试
    - **Property 8: 历史记录按时间倒序排列**
    - **Validates: Requirements 8.2**

  - [ ]* 11.6 编写新问辩不修改已有记录属性测试
    - **Property 9: 新问辩不修改已有记录**
    - **Validates: Requirements 3.7**

  - [ ]* 11.7 编写 HeyGenService 单元测试
    - 测试 token 生成成功/失败场景，mock HTTP 调用
    - 测试 HEYGEN_API_KEY 未配置时的错误处理
    - _Requirements: 11.3, 11.4_

  - [ ]* 11.8 编写 DefenseService 单元测试
    - 测试问题 CRUD 具体示例
    - 测试 submit_answer 完整流程（mock STT + AI）
    - 测试 STT 失败和 AI 反馈失败的错误场景
    - _Requirements: 2.2-2.6, 6.5, 7.1-7.6_

- [x] 12. Final checkpoint - 确保所有代码和测试完整
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis
- 后端使用 Python (FastAPI)，前端使用 TypeScript (React + Ant Design)
- HeyGen SDK (`@heygen/streaming-avatar`) 在前端运行，后端仅负责生成 access token
- 复用已有的 `stt_service.py`（Deepgram）和 `ai_utils.py`（通义千问）
