# Implementation Plan: System Optimization V2

## Overview

基于创赛评审系统（web_ui_agent）的第二轮系统优化实施计划。按照依赖关系排列：先完成数据模型和基础设施变更，再实现后端服务改造，最后完成前端组件增强。后端使用 Python/FastAPI，前端使用 TypeScript/React。

## Tasks

- [x] 1. 数据模型与基础设施准备
  - [x] 1.1 扩展 Supabase 数据库 schema
    - 在 `examples/web_ui_agent/backend/migrations/` 中创建迁移文件，添加 reviews 表的 `selected_materials`、`ppt_visual_review`、`presenter_evaluation`、`stt_transcript` 字段
    - 创建可选的 `api_timing_logs` 表
    - _Requirements: 3.1, 4.3, 6.3, 8.1, 11.6_

  - [x] 1.2 扩展后端 Pydantic schemas
    - 在 `app/models/schemas.py` 中新增 `PPTVisualDimension`、`PPTVisualReviewResult`、`PresenterEvaluation` 模型
    - 扩展 `ReviewResult` 添加 `selected_materials`、`ppt_visual_review`、`presenter_evaluation` 字段
    - 扩展 `MaterialStatusResponse` 添加 `presentation_audio` 字段
    - _Requirements: 3.1, 4.2, 4.3, 5.1, 8.1_

  - [x] 1.3 扩展前端 TypeScript 类型定义
    - 在 `frontend/src/types/index.ts` 中新增 `PPTVisualReviewResult`、`PPTVisualDimension`、`PresenterEvaluation` 接口
    - 扩展 `ReviewResult` 接口添加新字段
    - 扩展 `MaterialType` 和 `MaterialStatusResponse` 类型添加 `presentation_audio`
    - _Requirements: 3.2, 4.7, 5.4, 8.3_

- [x] 2. Checkpoint - 确保数据模型变更完整
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. PDF导出中文标签 (R1)
  - [x] 3.1 实现 ExportService 名称映射转换
    - 在 `app/services/export_service.py` 中导入 `COMPETITION_NAMES`、`TRACK_NAMES`、`GROUP_NAMES` 映射
    - 新增 `REVIEW_TYPE_LABELS` 字典和 `_resolve_name()` 函数
    - 改造 `_build_pdf()` 方法，对 competition/track/group/review_type 字段进行中文转换
    - 映射缺失时回退显示原始英文 ID
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 3.2 编写 _resolve_name 的 property test
    - **Property 1: Name resolution mapping**
    - 在 `backend/tests/` 中创建 `test_name_resolution.py`，使用 hypothesis 验证映射存在时返回映射值、不存在时返回原始值
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

- [x] 4. 文本评审服务改造 (R2, R3, R4)
  - [x] 4.1 简化 TextReviewService 材料类型校验
    - 修改 `app/services/text_review_service.py` 中 `VALID_MATERIAL_TYPES` 为 `{"text_ppt", "bp"}`
    - 修改错误提示为"请先上传文本PPT或BP材料"
    - _Requirements: 2.1, 2.3_

  - [ ]* 4.2 编写材料类型校验的 property test
    - **Property 2: Text review material type validation**
    - 在 `backend/tests/test_text_review.py` 中使用 hypothesis 验证仅 text_ppt 和 bp 被接受
    - **Validates: Requirements 2.1**

  - [x] 4.3 实现评审记录保存所选材料
    - 修改 `TextReviewService.review()` 在 insert 评审记录时写入 `selected_materials` 字段
    - _Requirements: 3.1_

  - [ ]* 4.4 编写 selected_materials 存储的 property test
    - **Property 3: Selected materials round-trip storage**
    - 验证存储后查询返回的 selected_materials 与原始输入一致
    - **Validates: Requirements 3.1**

  - [x] 4.5 创建 PPT 视觉评审 prompt 模板
    - 基于 `backend/文本PPT视觉.md` 创建 `backend/prompts/templates/ppt_visual_review.md`
    - 包含信息结构、信息密度、视觉设计、图示表达、说服力、完整性六个维度的评审指引和输出格式要求
    - 创建完成后删除 `backend/文本PPT视觉.md` 原始参考文件
    - _Requirements: 4.2, 4.5, 4.6_

  - [x] 4.6 实现 TextReviewService PPT 视觉评审功能
    - 在 `app/services/text_review_service.py` 中新增 `_ppt_visual_review()` 方法
    - 实现：下载 PPT → 上传 DashScope OSS → 组装 prompt → 调用 Qwen-VL-Max → 解析六维度结果
    - 在 `review()` 方法末尾，当 text_ppt 被选中时调用视觉评审
    - 视觉评审失败时降级处理（ppt_visual_review 为 null，不影响主流程）
    - _Requirements: 4.1, 4.3, 4.4_

  - [ ]* 4.7 编写 PPT 视觉评审结果结构的 property tests
    - **Property 6: PPT visual review has exactly six dimensions**
    - **Property 7: Excellent PPT rating produces no forced suggestions**
    - 在 `backend/tests/test_ppt_visual.py` 中使用 hypothesis 验证维度数量和优秀评级逻辑
    - **Validates: Requirements 4.2, 4.4**

- [x] 5. Checkpoint - 确保文本评审改造完成
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. STT 服务与离线评审改造 (R5, R6, R7, R8)
  - [x] 6.1 新增 Deepgram API Key 配置
    - 在 `app/config.py` 的 `Settings` 类中新增 `deepgram_api_key` 字段
    - 在 `.env.example` 中添加 `DEEPGRAM_API_KEY` 示例
    - _Requirements: 6.2_

  - [x] 6.2 实现 STTService
    - 新建 `app/services/stt_service.py`，实现 `STTService` 类
    - 使用 `httpx.AsyncClient` 调用 Deepgram REST API
    - 支持 `audio/mp4`、`audio/mpeg`、`audio/wav`、`audio/x-m4a`、`audio/aac` MIME 类型
    - 配置参数：`language=zh`、`model=nova-2`、`smart_format=true`
    - _Requirements: 6.1, 6.2_

  - [x] 6.3 扩展材料服务支持音频上传
    - 修改 `app/services/material_service.py` 支持 `presentation_audio` 材料类型
    - 支持 mp3、wav、m4a、aac 格式文件
    - _Requirements: 5.1, 5.2_

  - [ ]* 6.4 编写音频文件类型校验的 property test
    - **Property 8: Audio file type validation**
    - 在 `backend/tests/test_material.py` 中使用 hypothesis 验证音频格式接受/拒绝逻辑
    - **Validates: Requirements 5.1, 5.2**

  - [x] 6.5 改造 OfflineReviewService 支持音频 + STT + 视觉评审 + 路演者评价
    - 修改 `app/services/offline_review_service.py`：
      - 支持 `presentation_audio` 作为替代媒体源（视频或音频至少一种）
      - 集成 STTService 进行语音转文字
      - 将转录文本与 PPT 一起传给 Qwen-Long
      - 在 Qwen-Long 完成后调用 Qwen-VL-Max 进行 PPT 视觉评审（复用 prompt 模板）
      - 在 prompt 中新增路演表现评价维度，基于转录文本分析路演者表达
      - STT 失败时返回错误提示
    - _Requirements: 5.3, 6.1, 6.3, 6.4, 7.1, 7.2, 8.1, 8.2_

  - [ ]* 6.6 编写离线评审相关 property tests
    - **Property 9: Offline review media prerequisite**
    - **Property 10: STT transcript included in assembled prompt**
    - **Property 11: Offline review with PPT includes visual review**
    - **Property 12: Offline review result contains presenter evaluation**
    - 在 `backend/tests/test_offline_review.py` 中使用 hypothesis 验证
    - **Validates: Requirements 5.3, 6.3, 7.1, 8.1**

- [x] 7. Checkpoint - 确保离线评审改造完成
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. 现场路演 prompt 注入项目简介 (R9)
  - [x] 8.1 改造 LivePresentationService 注入项目简介
    - 修改 `app/services/live_presentation_service.py` 的 `start_session()` 方法
    - 查询 ProjectProfile，将非空字段拼接到 prompt 材料描述部分
    - Profile 不存在时保持当前行为不变
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 8.2 编写现场路演 prompt 注入的 property test
    - **Property 13: Live session prompt contains project profile fields**
    - 在 `backend/tests/test_live_presentation.py` 中使用 hypothesis 验证
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [x] 9. API 耗时监控 (R11)
  - [x] 9.1 实现后端 TimingMiddleware 和 TimingContext
    - 新建 `app/utils/timing_middleware.py`，实现 FastAPI 中间件记录请求总耗时
    - 新建 `app/utils/timing.py`，实现 `TimingContext` 上下文管理器记录外部服务调用耗时
    - 在 `app/main.py` 中注册 TimingMiddleware
    - _Requirements: 11.1, 11.2, 11.3, 11.5, 11.6_

  - [x] 9.2 在核心服务中集成 TimingContext
    - 在 TextReviewService、OfflineReviewService、LivePresentationService、ExportService 中使用 `TimingContext.track()` 包裹外部服务调用
    - _Requirements: 11.2, 11.5_

  - [x] 9.3 实现前端 axios 拦截器耗时日志
    - 在 `frontend/src/services/api.ts` 中添加请求/响应拦截器，记录前端侧 API 调用耗时到 console.log
    - _Requirements: 11.4_

  - [ ]* 9.4 编写 API timing 结构的 property test
    - **Property 14: API timing output structure**
    - 在 `backend/tests/test_timing.py` 中使用 hypothesis 验证耗时日志结构
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.6**

- [x] 10. 前端评审结果界面美化 (R10)
  - [x] 10.1 改造 TextReviewPanel 组件
    - 修改 `frontend/src/components/TextReviewPanel.tsx`：
      - 评分维度表格使用 Ant Design `Table` 组件，统一列宽和对齐
      - 子项评价使用 `Descriptions` 组件，统一缩进和分隔
      - 改进建议使用 `List` 组件，统一段落间距
      - 新增 PPT 视觉评审独立区块（`Card` 组件）
      - 添加响应式样式，确保不同屏幕宽度下不错位
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 4.7_

- [x] 11. 前端文本评审与离线评审页面改造
  - [x] 11.1 改造文本评审页面
    - 修改 `frontend/src/pages/TextReview.tsx`：仅展示 text_ppt 和 bp 两种材料选择项
    - _Requirements: 2.2_

  - [x] 11.2 改造评审历史页面
    - 修改 `frontend/src/pages/ReviewHistory.tsx`：在表格中新增"所选材料"列，以中文标签形式展示
    - _Requirements: 3.2_

  - [ ]* 11.3 编写材料标签解析的 property test
    - **Property 4: Material type label resolution for display**
    - 在 `frontend/src/__tests__/labelResolver.test.ts` 中使用 fast-check 验证标签解析逻辑
    - **Validates: Requirements 3.2**

  - [x] 11.4 改造评审详情页面
    - 修改 `frontend/src/pages/ReviewDetail.tsx`：展示所选材料列表、PPT 视觉评审区块、路演者评价区块
    - _Requirements: 3.3, 4.7, 7.3, 8.3_

  - [x] 11.5 改造离线评审页面
    - 修改 `frontend/src/pages/OfflineReview.tsx`：展示路演视频和路演音频两种媒体材料的上传状态
    - _Requirements: 5.4_

- [x] 12. Checkpoint - 确保前端页面改造完成
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. 前端用户引导与自动触发 (R12)
  - [x] 13.1 实现 OnboardingGuide 组件
    - 新建 `frontend/src/components/OnboardingGuide.tsx`
    - 使用 localStorage 存储引导状态，key 格式 `onboarding_${projectId}_${trigger}`
    - 关闭后同一项目内不再重复弹出
    - _Requirements: 12.1, 12.2_

  - [x] 13.2 实现自动触发 AI 项目简历总结
    - 在 `frontend/src/pages/MaterialCenter.tsx` 中，bp 或 text_ppt 上传成功后自动调用 profileApi.extract
    - 展示"正在生成项目简介..."处理中状态
    - 完成后替换为生成的 Profile 内容
    - 失败时展示错误提示 + 重试按钮
    - _Requirements: 12.3, 12.4, 12.5, 12.6_

  - [ ]* 13.3 编写 OnboardingGuide 和 AutoTrigger 的 property tests
    - **Property 15: Onboarding guide dismissal persistence**
    - **Property 16: Auto-trigger fires on bp/text_ppt upload**
    - 在 `frontend/src/__tests__/onboarding.test.ts` 和 `frontend/src/__tests__/autoTrigger.test.ts` 中使用 fast-check 验证
    - **Validates: Requirements 12.2, 12.3**

- [x] 14. 前端并发操作状态管理 (R13)
  - [x] 14.1 实现 useConcurrentState hook
    - 新建 `frontend/src/hooks/useConcurrentState.ts`
    - 为每个异步操作分配独立状态标识（upload_bp、upload_text_ppt、profile_extract、text_review、offline_review、export_pdf 等）
    - 实现 startOperation、completeOperation、failOperation、getStatus 方法
    - 支持组件卸载/重挂载后状态恢复
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 14.2 在 MaterialCenter 和相关页面集成 useConcurrentState
    - 替换现有的单一 loading 状态为 useConcurrentState 管理
    - 确保各操作状态互不干扰
    - _Requirements: 13.1, 13.2, 13.4, 13.6_

  - [ ]* 14.3 编写并发状态管理的 property tests
    - **Property 17: Concurrent state isolation**
    - **Property 18: Concurrent state persistence across navigation**
    - 在 `frontend/src/__tests__/concurrentState.test.ts` 中使用 fast-check 验证
    - **Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5, 13.6**

- [x] 15. Final checkpoint - 确保所有功能集成完成
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- 后端测试使用 pytest + hypothesis，前端测试使用 vitest + fast-check
- 每个 property test 至少运行 100 次迭代
- PPT 视觉评审失败时降级处理，不影响主评审流程
- STT 转录失败时离线评审整体失败（转录文本是核心输入）
