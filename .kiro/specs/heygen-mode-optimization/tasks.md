# 实施计划：HeyGen 模式优化

## 概述

基于需求和设计文档，将 HeyGen 模式全面升级：Avatar 类型区分、分类展示、差异化视频生成、丰富视频选项、多场景视频、Photo Avatar 创建、视频复用机制、Schema 更新。后端使用 Python (FastAPI)，前端使用 TypeScript (React + Ant Design)。

## Tasks

- [x] 1. 数据库迁移与 Schema 更新
  - [x] 1.1 创建数据库迁移脚本 `backend/migrations/007_heygen_mode_optimization.sql`
    - 为 `defense_video_tasks` 表新增 `config_hash TEXT`、`avatar_type TEXT`（含 CHECK 约束）、`video_options JSONB DEFAULT '{}'` 列
    - 创建条件索引 `idx_dvt_config_hash` (WHERE status = 'completed')
    - _Requirements: 7.3, 7.4_

  - [x] 1.2 在 `backend/app/models/schemas.py` 中新增 Pydantic 模型
    - 新增 `VideoGenerationOptions` 模型（avatar_id, voice_id, avatar_type, resolution, aspect_ratio, expressiveness, remove_background, voice_locale）
    - 新增 `PhotoAvatarCreateRequest` 模型（name, age, gender, ethnicity, orientation, pose, style, appearance，appearance 最长 1000 字符）
    - 新增 `PhotoAvatarStatusResponse` 模型（generation_id, status）
    - 扩展 `VideoTaskResponse` 新增 `is_reused: bool = False` 字段
    - 扩展 `GenerateQuestionVideoRequest` 新增视频选项字段（avatar_type, resolution, aspect_ratio, expressiveness, remove_background, voice_locale）
    - _Requirements: 8.1, 8.2, 8.3, 7.5_

  - [ ]* 1.3 编写 Schema 验证属性测试
    - **Property 8: 视频生成选项 Schema 验证**
    - **Property 9: Photo Avatar 创建 Schema 验证**
    - **Validates: Requirements 7.1, 4.7, 8.2**

- [x] 2. 后端配置与 Motion Prompt 模板
  - [x] 2.1 更新 `backend/app/config.py` 默认值
    - 将 `heygen_video_avatar_id` 默认值改为 `8d4aa85254354488a0f9bce7b4c3549e`
    - 将 `heygen_video_voice_id` 默认值改为 `769716d5135541db93e95ce84508c59e`
    - _Requirements: 1.4, 1.5_

  - [x] 2.2 创建 Motion Prompt 模板文件 `backend/prompts/templates/defense/motion_prompt.md`
    - 编写适用于 Photo Avatar 的动作描述提示词
    - _Requirements: 3.3_

- [x] 3. HeyGenVideoService 核心改造
  - [x] 3.1 改造 `list_avatars` 方法，返回 `avatar_type` 和 `is_custom` 字段
    - 根据 API 返回的 `avatar_type` 字段映射：`video_avatar` → `digital_twin`，`photo_avatar` 保持不变
    - 移除基于 ID 格式判断 `talking_photo` 的旧逻辑
    - 包含 `is_custom` 字段标识用户自有资源
    - _Requirements: 1.1, 1.2, 1.3, 2.4_

  - [ ]* 3.2 编写 Avatar 数据完整性属性测试
    - **Property 1: Avatar 数据完整性与类型映射**
    - **Validates: Requirements 1.1, 1.2, 2.4**

  - [x] 3.3 实现新版 `generate_video` 方法，支持差异化 Payload 构建
    - 使用新版 `POST /v2/videos` API 替代旧版 Studio API
    - Photo Avatar: 附加 `motion_prompt`（从模板加载）+ `expressiveness`
    - Digital Twin: 省略 `motion_prompt` 和 `expressiveness`
    - 始终设置 `caption: true`
    - 接收并映射所有视频选项参数（resolution, aspect_ratio, remove_background, voice_locale）
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 4.6, 4.8_

  - [ ]* 3.4 编写 Payload 差异化构建属性测试
    - **Property 2: 基于 Avatar 类型的 Payload 差异化构建**
    - **Validates: Requirements 3.1, 3.2, 3.4**

  - [ ]* 3.5 编写字幕始终开启属性测试
    - **Property 3: 字幕始终开启**
    - **Validates: Requirements 4.6**

  - [ ]* 3.6 编写视频选项映射属性测试
    - **Property 4: 视频选项正确映射**
    - **Validates: Requirements 4.8**

- [ ] 4. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 5. 背景图片生成与多场景视频
  - [x] 5.1 创建 `backend/app/services/avatar/background_generator.py`
    - 实现 `BackgroundImageGenerator.generate()` 方法
    - 使用 Pillow 生成包含问题序号和文字的 PNG 背景图片（默认 1920×1080）
    - 布局：左侧 40% 留给数字人，右侧 60% 显示问题文字，自动换行
    - 统一配色：深蓝渐变背景 + 白色文字
    - 处理字体缺失回退、文字过长自动换行缩小
    - _Requirements: 5.2, 5.3_

  - [ ]* 5.2 编写背景图片生成属性测试
    - **Property 6: 背景图片生成有效性**
    - **Validates: Requirements 5.2, 5.3**

  - [x] 5.3 在 HeyGenVideoService 中实现 `upload_asset` 和 `generate_multi_scene_video` 方法
    - `upload_asset`: 通过 `POST /v2/asset` 上传图片，返回 asset_id
    - `generate_multi_scene_video`: 使用 Studio API (`POST /v2/video/generate`) 构建多场景 payload
    - 第一个场景为开场白（纯色背景 `"color"` 类型）
    - 后续场景各对应一个问题（`"image"` 类型背景，avatar scale < 1.0，offset 偏移到一侧）
    - 始终开启 `caption: true`
    - _Requirements: 5.1, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 5.4 编写多场景结构属性测试
    - **Property 5: 多场景结构正确性**
    - **Validates: Requirements 5.1, 5.6**

  - [ ]* 5.5 编写问题场景缩放偏移属性测试
    - **Property 7: 问题场景数字人缩放与偏移**
    - **Validates: Requirements 5.4**

- [x] 6. VideoTaskService 改造与视频复用
  - [x] 6.1 改造 `create_question_video_task` 方法
    - 接收新增视频选项参数（avatar_type, resolution, aspect_ratio, expressiveness, remove_background, voice_locale）
    - 将问题拆分为多个场景，调用 `BackgroundImageGenerator` 生成背景图，上传 asset
    - 调用 `generate_multi_scene_video` 替代 `generate_video`
    - config_hash 计算纳入所有视频选项参数
    - 插入记录时保存 `avatar_type` 和 `video_options` (JSONB)
    - 复用逻辑：匹配 config_hash + status=completed 时返回已有记录并标记 `is_reused=true`
    - _Requirements: 5.1, 7.1, 7.2, 7.3_

  - [x] 6.2 改造 `create_feedback_video_task` 方法
    - 传递视频选项参数给 `generate_video`（单场景，使用新版 API）
    - _Requirements: 3.1, 3.2, 4.8_

  - [ ]* 6.3 编写 config_hash 完整性属性测试
    - **Property 10: config_hash 完整性与复用正确性**
    - **Validates: Requirements 7.1, 7.2**

- [x] 7. Defense Route 更新
  - [x] 7.1 扩展 `generate_question_video` 端点，接收新增视频选项参数
    - 使用扩展后的 `GenerateQuestionVideoRequest` 模型
    - 将参数传递给 `VideoTaskService`
    - 响应中包含 `is_reused` 字段
    - _Requirements: 4.7, 7.5_

  - [x] 7.2 新增 Photo Avatar 端点
    - `POST /avatar/heygen/photo-avatar`: 创建 Photo Avatar
    - `GET /avatar/heygen/photo-avatar/{generation_id}`: 查询创建状态
    - 在 HeyGenVideoService 中实现 `create_photo_avatar` 和 `check_photo_avatar_status` 方法
    - _Requirements: 6.3, 6.4, 6.7_

- [ ] 8. Checkpoint - 确保所有后端测试通过
  - 确保所有测试通过，ask the user if questions arise.

- [x] 9. 前端类型与 API 更新
  - [x] 9.1 更新 `frontend/src/types/index.ts`
    - 新增 `AvatarInfo` 接口（含 avatar_type, is_custom）
    - 新增 `VideoGenerationOptions` 接口
    - 新增 `PhotoAvatarCreateParams` 接口
    - 扩展 `VideoTask` 类型新增 `is_reused` 字段
    - _Requirements: 1.2, 8.1, 8.2_

  - [x] 9.2 更新 `frontend/src/services/api.ts`
    - 修改 `listHeygenAvatars` 返回类型为 `AvatarInfo[]`
    - 修改 `generateQuestionVideo` 接收 `VideoGenerationOptions` 参数
    - 新增 `createPhotoAvatar` API 方法
    - 新增 `checkPhotoAvatarStatus` API 方法
    - _Requirements: 6.3, 6.4, 4.7_

- [x] 10. 前端 DigitalDefense 页面改造
  - [x] 10.1 Avatar/Voice 选择器改为分组模式
    - Avatar 选择器使用 `<Select.OptGroup>` 分为"我的"和"公共"两组
    - "我的"分组中显示类型标签（Photo Avatar / Digital Twin）
    - "我的"分组显示在"公共"分组之前
    - Voice 选择器同样改为分组模式（"我的" / "公共"）
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 10.2 新增视频选项面板
    - 语音语种选择（默认 zh-CN）
    - 分辨率选择（1080p / 720p，默认 720p）
    - 宽高比选择（16:9 / 9:16，默认 16:9）
    - 表情丰富度选择（仅 Photo Avatar 时显示，low / medium / high，默认 medium）
    - 背景移除开关（默认关闭）
    - 将所有选项参数传递给 `generateQuestionVideo` API
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [x] 10.3 新增 Photo Avatar 创建功能
    - 在数字人选择区域添加"创建 Photo Avatar"按钮
    - 弹出 Modal 表单收集必填信息（name, age, gender, ethnicity, orientation, pose, style, appearance）
    - 表单中显示提示："如需效果更好的 Digital Twin，请前往 HeyGen 官网创建"
    - 提交后显示创建状态，提供查询进度功能
    - _Requirements: 6.1, 6.2, 6.5, 6.6_

  - [x] 10.4 视频复用状态展示
    - 收到 `is_reused=true` 时显示 `msg.success('复用已有视频，无需重新生成')`，跳过轮询直接进入 ready 状态
    - 收到 `is_reused=false` 时正常进入生成中状态并开始轮询
    - VideoTaskStatus 组件根据 `is_reused` 显示不同标签（"已复用" vs "已生成"）
    - _Requirements: 7.5, 7.6, 7.7_

- [ ] 11. 单元测试
  - [ ]* 11.1 编写后端单元测试 `backend/tests/test_heygen_unit.py`
    - 测试默认 avatar_id 和 voice_id 配置值
    - 测试 motion_prompt 模板加载
    - 测试 Photo Avatar 端点存在性
    - 测试背景图片中文文字生成
    - 测试开场白场景纯色背景
    - 测试 config_hash 包含新增选项
    - 测试 config_hash 选项变化导致不同值
    - 测试视频复用返回 is_reused 标识
    - _Requirements: 1.4, 1.5, 3.3, 6.3, 5.3, 5.6, 7.1, 7.2, 7.5_

- [ ] 12. Final checkpoint - 确保所有测试通过
  - 确保所有测试通过，ask the user if questions arise.

## Notes

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了具体的需求编号以确保可追溯性
- 属性测试验证设计文档中定义的 10 个正确性属性
- 后端测试使用 Hypothesis 库进行属性测试，pytest 进行单元测试
- 前端测试可使用 Vitest + React Testing Library（未列为必须任务）
