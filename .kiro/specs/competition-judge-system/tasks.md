# Implementation Plan: 中国大学生创新大赛AI评委系统

## Overview

基于FastAPI（后端）+ React/TypeScript（前端）+ Supabase（数据库）的AI评委系统实现计划。按照从基础架构到核心功能再到集成的顺序，逐步构建完整系统。所有代码部署在 `examples/web_ui_agent/` 目录下。

## Tasks

- [x] 1. 后端项目结构与基础配置
  - [x] 1.1 初始化后端项目结构和依赖配置
    - 清理 `examples/web_ui_agent/backend/` 下的旧文件（simple_agent_example.py, test_simple_agent.py, instructions.md）
    - 创建 `app/` 目录结构：`__init__.py`, `main.py`, `config.py`, `routes/`, `services/`, `models/`, `utils/`
    - 更新 `pyproject.toml`：添加 fastapi, uvicorn, supabase, python-multipart, python-pptx, Pillow, httpx, pydantic, hypothesis 等依赖，移除 `[tool.uv.sources]` 及之后内容
    - 创建 `.env.example` 列出所有环境变量（SUPABASE_URL, SUPABASE_KEY, DASHSCOPE_API_KEY, GETSTREAM_API_KEY 等）
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [x] 1.2 实现配置管理和Supabase客户端初始化
    - 创建 `app/config.py`：使用 pydantic-settings 从环境变量加载配置
    - 创建 `app/models/database.py`：初始化 Supabase 客户端（Auth + Storage + DB）
    - 创建 `app/main.py`：FastAPI 应用入口，注册CORS中间件和路由
    - _Requirements: 10.1, 10.2, 12.1_

  - [x] 1.3 定义Pydantic数据模型（schemas.py）
    - 创建 `app/models/schemas.py`：定义所有请求/响应模型
    - 包含：EvaluationDimension, EvaluationRules, MaterialUploadResponse, ReviewRequest, DimensionScore, ReviewResult, CompetitionInfo, TrackInfo, GroupInfo, ProjectCreate, ProjectResponse, LiveSessionCreate, ModeSwitch, JudgeStyleInfo, PresetVoiceInfo, CustomVoiceInfo, ErrorResponse
    - _Requirements: 12.2, 12.3, 12.4, 12.5_

  - [x] 1.4 创建统一错误处理中间件和工具函数
    - 创建 `app/utils/file_utils.py`：文件格式验证、大小检查工具函数
    - 创建 `app/utils/ai_utils.py`：AI API调用封装（含重试逻辑、超时配置）
    - 在 `app/main.py` 中注册全局异常处理器，统一返回 ErrorResponse 格式
    - _Requirements: 4.7, 3.7, 3.8_

- [x] 2. 赛事配置与评审规则服务
  - [x] 2.1 实现RuleService（评审规则加载服务）
    - 创建 `app/services/rule_service.py`
    - 实现 `list_competitions()`：扫描 `rules/` 目录返回赛事列表
    - 实现 `list_tracks(competition)`：扫描赛事子目录返回赛道列表
    - 实现 `list_groups(competition, track)`：扫描赛道子目录返回组别列表
    - 实现 `has_rules(competition, track, group)`：检查规则文件是否存在
    - 实现 `load_rules(competition, track, group)`：加载并解析评审规则文件，提取维度和分值
    - 支持 .md, .pdf, .docx, .xlsx 格式的规则文件读取
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3, 2.4_

  - [ ]* 2.2 编写RuleService属性测试
    - **Property 1: 赛事级联选择一致性**
    - **Property 2: 无规则组合的错误处理**
    - **Property 3: 评审规则路径构造正确性**
    - **Property 4: 评审规则维度完整性**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.5, 2.3, 2.4**

  - [x] 2.3 实现KnowledgeService（知识库加载服务）
    - 创建 `app/services/knowledge_service.py`
    - 实现 `load_knowledge(material_type)`：从 `knowledge/{bp,text_ppt,presentation_ppt,presentation}/` 加载知识库内容
    - 支持 .md, .pdf, .docx, .xlsx 格式
    - _Requirements: 2.5, 2.6, 2.7_

  - [x] 2.4 创建赛事配置路由和示例规则文件
    - 创建 `app/routes/competitions.py`：实现赛事/赛道/组别查询和规则加载的API端点
    - 创建 `rules/` 目录结构和至少一个示例规则文件（如 `rules/guochuangsai/gaojiao/benke_chuangyi/rules.md`）
    - 创建 `knowledge/` 目录结构和示例知识库文件
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.5_

- [ ] 3. 用户认证与项目管理
  - [ ] 3.1 实现AuthService和认证路由
    - 创建 `app/services/auth_service.py`：封装 Supabase Auth（注册、登录、获取当前用户）
    - 创建 `app/routes/auth.py`：实现 `/api/auth/register`, `/api/auth/login`, `/api/auth/me` 端点
    - 实现JWT token验证依赖项（FastAPI Depends）
    - _Requirements: 9.1_

  - [ ] 3.2 实现ProjectService和项目管理路由
    - 创建 `app/services/project_service.py`：项目CRUD操作（创建、列表、详情、更新）
    - 创建 `app/routes/projects.py`：实现项目管理API端点
    - 项目创建时验证必填字段（名称、赛事、赛道、组别）
    - 项目列表返回材料上传状态和当前比赛阶段
    - _Requirements: 9.2, 9.3, 9.4, 9.5, 9.7_

  - [ ]* 3.3 编写项目管理属性测试
    - **Property 14: 项目创建字段验证**
    - **Property 15: 项目与评审记录的CRUD一致性**
    - **Property 16: 项目数据持久化往返**
    - **Validates: Requirements 9.2, 9.3, 9.5, 9.6, 12.3**

- [ ] 4. 材料管理服务
  - [ ] 4.1 实现MaterialService（材料上传与管理）
    - 创建 `app/services/material_service.py`
    - 实现 `upload(project_id, material_type, file)`：上传文件到Supabase Storage，记录版本信息，将旧版本 `is_latest` 设为 false
    - 实现 `get_latest(project_id, material_type)`：获取最新版本材料
    - 实现 `get_versions(project_id, material_type)`：获取材料历史版本列表
    - 实现文件格式验证（BP: .docx/.pdf, PPT: .pptx/.pdf, 视频: .mp4/.webm）
    - 实现文件大小验证（PPT/BP ≤ 50MB, 视频 ≤ 500MB）
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ] 4.2 实现PPTConvertService（PPT转图像）
    - 创建 `app/services/ppt_convert_service.py`
    - 实现 `convert_to_images(file_path)`：使用 python-pptx + Pillow 或 LibreOffice 将PPT每页转为PNG图像
    - 上传PPT后自动触发转换，将图像路径存储到 `project_materials.image_paths`
    - _Requirements: 3.9_

  - [ ] 4.3 实现材料管理路由
    - 创建 `app/routes/materials.py`：实现材料上传、查询、版本历史的API端点
    - 上传端点在保存文件后，若为PPT类型则自动调用PPTConvertService转换
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.9_

  - [ ]* 4.4 编写材料管理属性测试
    - **Property 6: 文件格式与大小验证**
    - **Property 7: 材料版本管理一致性**
    - **Property 8: PPT转图像完整性**
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.7, 3.8, 3.9**

- [ ] 5. Checkpoint - 确保基础服务测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Prompt模板与评委风格服务
  - [ ] 6.1 实现PromptService（Prompt模板管理）
    - 创建 `app/services/prompt_service.py`
    - 实现 `list_styles()`：扫描 `prompts/styles/` 目录返回可用评委风格列表
    - 实现 `load_style(style_id)`：加载指定风格的角色描述Markdown文件
    - 实现 `load_template(template_name)`：加载功能模板（text_review/live_presentation/offline_review）
    - 实现 `assemble_prompt(template_name, style_id, rules_content, knowledge_content, material_content, interaction_mode)`：按顺序拼接最终prompt（角色描述→评审规则→知识库→材料→输出格式）
    - _Requirements: 13.1, 13.2, 13.5, 13.6, 13.7_

  - [ ] 6.2 创建Prompt模板文件和评委风格文件
    - 创建 `prompts/templates/text_review.md`：文本评审prompt模板（含占位符）
    - 创建 `prompts/templates/live_presentation.md`：现场路演prompt模板
    - 创建 `prompts/templates/offline_review.md`：离线评审prompt模板
    - 创建 `prompts/styles/strict.md`：严厉型评委角色描述
    - 创建 `prompts/styles/gentle.md`：温和型评委角色描述
    - 创建 `prompts/styles/academic.md`：学术型评委角色描述
    - _Requirements: 13.2, 13.3, 13.8_

  - [ ] 6.3 实现评委风格路由
    - 创建或扩展路由：实现 `GET /api/judge-styles` 端点
    - _Requirements: 13.4_

  - [ ]* 6.4 编写PromptService属性测试
    - **Property 5: 评审Prompt组装完整性**
    - **Property 18: Prompt模板组装顺序正确性**
    - **Property 19: 评委风格切换有效性**
    - **Property 20: 交互模式与评委风格独立性**
    - **Validates: Requirements 2.8, 13.5, 13.6, 13.7**

- [ ] 7. AI文本评审服务
  - [ ] 7.1 实现TextReviewService（AI文本评审）
    - 创建 `app/services/text_review_service.py`
    - 实现 `review(project_id, user_id, stage, judge_style)`：
      1. 从MaterialService获取最新文本PPT和文本BP
      2. 从RuleService加载评审规则
      3. 从KnowledgeService加载 `text_ppt` 和 `bp` 知识库
      4. 通过PromptService组装prompt
      5. 调用通义千问多模态API（发送PPT图像+BP文本+prompt）
      6. 解析AI返回结果为DimensionScore列表
      7. 存储评审记录到Supabase（reviews + review_details表）
    - 处理仅有PPT无BP的情况（降级评审并提示）
    - 实现AI API调用失败的重试和错误处理
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [ ] 7.2 实现评审路由（文本评审+结果查询+导出）
    - 创建 `app/routes/reviews.py`
    - 实现 `POST /api/projects/{id}/reviews/text`：发起文本评审
    - 实现 `GET /api/projects/{id}/reviews`：获取评审记录列表
    - 实现 `GET /api/projects/{id}/reviews/{review_id}`：获取评审详情（含维度评分和建议）
    - 实现 `GET /api/projects/{id}/reviews/{review_id}/export`：导出评审报告为PDF
    - _Requirements: 4.1, 4.6, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 9.5, 9.6_

  - [ ]* 7.3 编写文本评审属性测试
    - **Property 9: 评审结果使用最新材料**
    - **Property 10: 评审结果结构符合规则**
    - **Property 11: 评审结果持久化往返**
    - **Property 17: 评审记录类型与材料版本关联**
    - **Validates: Requirements 4.1, 4.3, 4.6, 12.5**

- [ ] 8. 离线路演评审服务
  - [ ] 8.1 实现OfflineReviewService（离线路演评审）
    - 创建 `app/services/offline_review_service.py`
    - 实现 `review(project_id, user_id, stage, judge_style)`：
      1. 从MaterialService获取最新路演PPT和路演视频
      2. 验证两种材料均已上传，否则返回提示
      3. 加载评审规则和路演相关知识库
      4. 通过PromptService组装prompt
      5. 调用通义千问多模态API分析视频+PPT
      6. 生成综合评审报告（演讲表现、PPT内容、综合评分、改进建议）
      7. 存储评审记录
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 8.2 扩展评审路由支持离线评审
    - 在 `app/routes/reviews.py` 中添加 `POST /api/projects/{id}/reviews/offline` 端点
    - _Requirements: 8.1_

  - [ ]* 8.3 编写离线评审属性测试
    - **Property 13: 离线评审报告完整性**
    - **Validates: Requirements 8.3, 8.4**

- [ ] 9. Checkpoint - 确保评审服务测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. 音色管理服务
  - [ ] 10.1 实现VoiceService（音色管理）
    - 创建 `app/services/voice_service.py`
    - 实现 `list_preset_voices()`：返回Qwen-Omni-Realtime的49种预设音色列表（含中文名称和描述）
    - 实现 `clone_voice(user_id, audio_file, preferred_name)`：验证音频格式/大小/时长，调用 `qwen-voice-enrollment` API，存储voice标识到 `custom_voices` 表
    - 实现 `list_custom_voices(user_id)`：查询用户自定义音色列表
    - 实现 `delete_custom_voice(user_id, voice_id)`：删除自定义音色
    - 实现 `get_voice_for_session(voice_id, voice_type)`：根据音色类型返回session.update参数
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7_

  - [ ] 10.2 实现音色管理路由
    - 创建 `app/routes/voices.py`（或在现有路由中扩展）
    - 实现 `GET /api/voices/presets`、`GET /api/voices/custom`、`POST /api/voices/clone`、`DELETE /api/voices/custom/{voice_id}` 端点
    - _Requirements: 14.1, 14.4, 14.6, 14.9_

  - [ ]* 10.3 编写音色管理属性测试
    - **Property 21: 预设音色设置正确性**
    - **Property 22: 声音复刻音频验证**
    - **Validates: Requirements 14.3, 14.4, 14.9**

- [ ] 11. 现场路演服务
  - [ ] 11.1 实现LivePresentationService（现场路演）
    - 创建 `app/services/live_presentation_service.py`
    - 实现 `start_session(project_id, user_id, mode, style, voice, voice_type)`：
      1. 从MaterialService获取最新路演PPT
      2. 加载评审规则和路演知识库
      3. 通过PromptService组装prompt（含交互模式指令）
      4. 通过VoiceService获取音色参数
      5. 创建GetStream视频通话会话
      6. 建立Qwen Realtime WebSocket连接，发送session.update（含voice参数和prompt）
    - 实现 `switch_mode(session_id, mode)`：切换提问/建议模式，仅替换prompt中交互模式指令部分
    - 实现 `end_session(session_id)`：结束路演会话，生成评审总结并存储
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ] 11.2 实现现场路演路由
    - 创建 `app/routes/live_presentation.py`
    - 实现 `POST /api/projects/{id}/live/start`、`POST /api/projects/{id}/live/mode`、`POST /api/projects/{id}/live/end` 端点
    - _Requirements: 6.1, 7.1, 7.4_

  - [ ]* 11.3 编写现场路演属性测试
    - **Property 12: 路演交互模式指令差异性**
    - **Validates: Requirements 7.2, 7.3**

- [ ] 12. Checkpoint - 确保后端所有服务测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. 前端项目初始化与基础组件
  - [ ] 13.1 初始化React + TypeScript前端项目
    - 在 `examples/web_ui_agent/frontend/` 下使用 Vite 初始化 React + TypeScript 项目
    - 安装依赖：antd（UI组件库）、axios（HTTP客户端）、recharts（图表）、@stream-io/video-react-sdk（GetStream视频）、react-router-dom
    - 配置 `tsconfig.json`、`vite.config.ts`（API代理到后端）
    - 创建 `src/types/` 目录，定义与后端对应的TypeScript类型
    - 创建 `src/services/api.ts`：封装axios实例和API调用函数
    - _Requirements: 11.1, 11.2, 11.6_

  - [ ] 13.2 实现认证页面和路由守卫
    - 创建 `src/pages/Login.tsx` 和 `src/pages/Register.tsx`
    - 实现认证上下文（AuthContext）管理登录状态和token
    - 实现路由守卫（ProtectedRoute），未登录跳转登录页
    - _Requirements: 9.1, 11.3_

  - [ ] 13.3 实现项目管理页面
    - 创建 `src/pages/ProjectList.tsx`：项目列表页，展示用户所有项目和创建入口
    - 创建 `src/pages/ProjectCreate.tsx`：项目创建页，包含 `CompetitionSelector` 三级联动选择器
    - 创建 `src/pages/ProjectDashboard.tsx`：项目概览仪表盘，展示比赛阶段进度和各阶段评审状态
    - 创建 `src/components/CompetitionSelector.tsx`：赛事/赛道/组别三级联动选择组件
    - _Requirements: 1.1, 1.2, 1.3, 9.2, 9.3, 9.4, 9.7, 11.4_

- [ ] 14. 前端核心功能页面
  - [ ] 14.1 实现材料中心页面
    - 创建 `src/pages/MaterialCenter.tsx`：展示四大核心材料上传状态和操作
    - 实现文件上传组件（含格式和大小前端校验）
    - 实现材料版本历史查看
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ] 14.2 实现文本评审页面和结果展示
    - 创建 `src/pages/TextReview.tsx`：发起文本评审页面，包含 `JudgeStyleSelector` 评委风格选择器
    - 创建 `src/components/TextReviewPanel.tsx`：评审结果展示面板
    - 创建 `src/components/RadarChart.tsx`：评分雷达图组件（使用recharts，维度标签和满分值动态调整）
    - 创建 `src/components/JudgeStyleSelector.tsx`：评委风格选择器（严厉型/温和型/学术型）
    - 展示各维度评分、子项评价、改进建议
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 13.4_

  - [ ] 14.3 实现评审历史页面
    - 创建 `src/pages/ReviewHistory.tsx`：评审记录列表，区分文本评审和路演评审
    - 创建 `src/pages/ReviewDetail.tsx`：评审详情页面，含导出PDF功能
    - _Requirements: 5.5, 5.6, 9.5, 9.6_

  - [ ] 14.4 实现现场路演页面
    - 创建 `src/pages/LivePresentation.tsx`：现场路演页面
    - 集成GetStream Video SDK实现音视频通话
    - 创建 `src/components/ModeSwitch.tsx`：提问/建议模式切换组件，清晰标识当前模式
    - 创建 `src/components/VoiceSelector.tsx`：音色选择器（预设音色+自定义音色列表）
    - 创建 `src/components/VoiceClonePanel.tsx`：声音复刻面板（上传音频、录音指南、状态提示）
    - 实现音色试听功能
    - 自定义音色选择时提示TTS合成模式延迟较高
    - _Requirements: 6.1, 6.6, 7.1, 7.5, 11.5, 14.1, 14.2, 14.6, 14.7, 14.8_

  - [ ] 14.5 实现离线路演评审页面
    - 创建 `src/pages/OfflineReview.tsx`：离线路演评审页面
    - 展示评审进度和结果（演讲表现、PPT内容、综合评分、改进建议）
    - _Requirements: 8.1, 8.3, 8.4_

- [ ] 15. 前端布局与响应式设计
  - [ ] 15.1 实现应用布局和首页
    - 创建 `src/components/AppLayout.tsx`：统一布局组件（导航栏、侧边栏）
    - 创建 `src/pages/Home.tsx`：首页，提供PPT评审和现场路演两个功能入口
    - 配置 `react-router-dom` 路由表
    - 实现响应式布局适配桌面端和移动端
    - _Requirements: 11.3, 11.4_

- [ ] 16. 部署配置
  - [ ] 16.1 创建Docker部署配置
    - 创建 `examples/web_ui_agent/backend/Dockerfile`：后端容器化配置
    - 创建 `examples/web_ui_agent/docker-compose.yml`：编排前后端服务
    - _Requirements: 10.6_

- [ ] 17. Checkpoint - 确保前后端集成测试通过
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. 数据库迁移脚本
  - [ ] 18.1 创建Supabase数据库迁移SQL
    - 创建 `examples/web_ui_agent/backend/migrations/` 目录
    - 编写SQL迁移脚本：创建 profiles, projects, project_materials, reviews, review_details, custom_voices 表及索引
    - 包含 RLS（Row Level Security）策略：用户只能访问自己的项目和评审记录
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [ ] 19. Final Checkpoint - 确保所有测试通过
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (22 properties total)
- Backend uses Python (FastAPI), frontend uses React + TypeScript
- All code deploys to `examples/web_ui_agent/` directory
