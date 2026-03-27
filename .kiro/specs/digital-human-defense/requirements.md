# Requirements Document

## Introduction

"数字人问辩"功能为 AI 评委系统新增一个与"文本评审"、"离线评审"、"现场路演"并列的功能模块。该功能集成 HeyGen Streaming Avatar API，创建数字人评委形象，通过预定义问题向用户提问，录制用户回答并利用 STT 转文字，再由 AI 根据项目全部上下文生成简短反馈，最终由数字人评委口述反馈。全流程（问题、回答、反馈）记录到数据库，支持历史查看。

## Glossary

- **Defense_System**: 数字人问辩功能的整体系统，包含前端页面、后端 API 和 HeyGen 集成
- **Predefined_Question**: 评委预先问题，由 AI 在项目简介提取时自动生成，用户可 CRUD 管理，每个问题不超过 40 个字
- **Avatar_Session**: 通过 HeyGen Streaming Avatar API 创建的数字人会话，用于数字人评委的视频渲染和语音播放
- **Defense_Session**: 一次完整的问辩会话，包含数字人提问、用户回答、AI 反馈三个阶段
- **Defense_Record**: 单次问辩的完整记录，包含预定义问题、用户回答文本、AI 反馈文本和时间戳
- **STT_Service**: 已有的 Deepgram 语音转文字服务，用于将用户回答录音转为文本
- **AI_Feedback_Service**: 利用通义千问 API 根据项目上下文生成 20-60 字中文反馈的服务
- **Project_Profile**: 已有的 AI 提取项目简介，包含团队介绍、领域、创业状态等结构化字段
- **HeyGen_API**: HeyGen Streaming Avatar API，用于创建和控制数字人评委的流式视频会话
- **Answer_Duration**: 用户回答的倒计时时长，默认 30 秒，用户可在问辩开始前修改

## Requirements

### Requirement 1: 预定义问题自动生成

**User Story:** As a 参赛团队用户, I want 系统在提取项目简介时自动生成 3 个评委预先问题, so that 我进入数字人问辩时已有可用的提问内容。

#### Acceptance Criteria

1. WHEN Project_Profile 提取完成, THE Defense_System SHALL 同时调用 AI 生成 3 个 Predefined_Question 并存储到数据库
2. THE Defense_System SHALL 确保每个 Predefined_Question 的字数不超过 40 个中文字符
3. THE Defense_System SHALL 基于 Project_Profile 的内容（团队介绍、领域、创业状态、已有成果、下一步目标）生成与项目相关的评委问题
4. WHEN AI 生成的某个问题超过 40 字, THE Defense_System SHALL 截断或重新生成该问题以满足字数限制
5. THE Defense_System SHALL 将生成的 Predefined_Question 存储在 `defense_questions` 数据库表中，关联到对应的 project_id

### Requirement 2: 预定义问题 CRUD 管理

**User Story:** As a 参赛团队用户, I want 能够新增、编辑、删除预定义问题, so that 我可以自定义数字人评委的提问内容。

#### Acceptance Criteria

1. THE Defense_System SHALL 在项目仪表盘的项目简介下方显示所有 Predefined_Question 列表
2. WHEN 用户点击"新增问题"按钮, THE Defense_System SHALL 允许用户输入一个不超过 40 字的新问题并保存到数据库
3. WHEN 用户点击某个问题的"编辑"按钮, THE Defense_System SHALL 允许用户修改该问题内容并保存，修改后的内容不超过 40 字
4. WHEN 用户点击某个问题的"删除"按钮, THE Defense_System SHALL 从数据库中删除该问题
5. IF 用户输入的问题内容超过 40 个中文字符, THEN THE Defense_System SHALL 阻止提交并提示"问题不能超过40个字"
6. IF 用户输入的问题内容为空, THEN THE Defense_System SHALL 阻止提交并提示"问题内容不能为空"

### Requirement 3: 数字人问辩入口与前置条件

**User Story:** As a 参赛团队用户, I want 在满足前置条件时才能进入数字人问辩, so that 问辩流程有足够的问题内容支撑。

#### Acceptance Criteria

1. THE Defense_System SHALL 在项目仪表盘的快捷操作区域显示"数字人问辩"功能卡片，与"文本评审"、"离线评审"等并列
2. WHILE Predefined_Question 数量为 0, THE Defense_System SHALL 禁用"数字人问辩"功能卡片并显示提示"请先添加至少一个评委问题"
3. WHILE Predefined_Question 数量大于等于 1, THE Defense_System SHALL 启用"数字人问辩"功能卡片，允许用户点击进入
4. WHEN 用户点击"数字人问辩"功能卡片, THE Defense_System SHALL 立即调用 HeyGen_API 创建 Avatar_Session（使用 avatar_id: 80d4afa941c243beb0a1116c95ea48ee）
5. WHEN 用户进入数字人问辩页面, THE Defense_System SHALL 先显示历史 Defense_Record 列表、Answer_Duration 设置框（默认 30 秒）和"开始问辩"按钮
6. WHILE Predefined_Question 数量大于等于 1, THE Defense_System SHALL 始终启用"开始问辩"按钮，无论该项目是否已有历史 Defense_Record
7. WHEN 用户已有历史 Defense_Record 并再次点击"开始问辩", THE Defense_System SHALL 启动一次全新的问辩流程并生成新的 Defense_Record，不覆盖或修改已有记录

### Requirement 4: HeyGen Streaming Avatar 会话管理

**User Story:** As a 参赛团队用户, I want 系统自动管理数字人评委的会话生命周期, so that 我无需关心底层技术细节即可与数字人评委互动。

#### Acceptance Criteria

1. WHEN 用户进入数字人问辩页面, THE Defense_System SHALL 调用 HeyGen Streaming Avatar API 的 createStreamingSession 接口创建会话
2. THE Defense_System SHALL 使用配置的 HeyGen API Key 和 avatar_id（80d4afa941c243beb0a1116c95ea48ee）创建 Avatar_Session
3. WHEN Avatar_Session 创建成功, THE Defense_System SHALL 通过 WebRTC 建立与 HeyGen 服务器的视频流连接
4. WHEN 问辩流程结束（所有问题回答完毕或用户主动结束）, THE Defense_System SHALL 调用 HeyGen_API 关闭 Avatar_Session 释放资源
5. WHEN 用户离开数字人问辩页面（包括导航离开、关闭浏览器标签页或关闭浏览器窗口）, THE Defense_System SHALL 自动调用 HeyGen_API 关闭当前 Avatar_Session 释放资源，避免内存泄漏
6. IF Avatar_Session 创建失败, THEN THE Defense_System SHALL 显示错误提示"数字人服务暂时不可用，请稍后重试"
7. IF Avatar_Session 在问辩过程中断开, THEN THE Defense_System SHALL 提示用户连接已断开并提供重新连接选项

### Requirement 5: 数字人评委提问流程

**User Story:** As a 参赛团队用户, I want 数字人评委以自然语言向我提出预定义问题, so that 问辩体验接近真实评委面试。

#### Acceptance Criteria

1. WHEN 用户点击"开始问辩"按钮, THE Defense_System SHALL 检查 Avatar_Session 是否已加载就绪
2. WHILE Avatar_Session 尚未加载完成, THE Defense_System SHALL 显示"数字人评委正在入场…"的加载提示
3. WHEN Avatar_Session 加载完成, THE Defense_System SHALL 显示数字人评委视频画面
4. THE Defense_System SHALL 通过 HeyGen_API 的 speak 接口让数字人评委朗读组合后的提问文本
5. THE Defense_System SHALL 将所有 Predefined_Question 组合为一段自然语言，格式为："你好，我是数字人评委，对于你们的{项目名称}项目，我有以下{问题数量}个问题：第一，{问题1}；第二，{问题2}；第三，{问题3}"
6. THE Defense_System SHALL 根据问题序号使用不同的序数词（如"首先"、"其次"、"第三"等）使语言更自然

### Requirement 6: 用户回答录音与 STT 转写

**User Story:** As a 参赛团队用户, I want 在数字人评委提问后进行限时回答并自动转为文字, so that AI 能基于我的回答生成反馈。

#### Acceptance Criteria

1. WHEN 数字人评委朗读完所有问题, THE Defense_System SHALL 立即开始 Answer_Duration 倒计时并同时开启浏览器麦克风录音
2. WHILE 用户正在录音回答, THE Defense_System SHALL 在页面上显示动态语音波形可视化效果，实时反映麦克风音频输入的音量变化
3. THE Defense_System SHALL 在页面上显示倒计时进度（剩余秒数）
4. WHEN 倒计时结束, THE Defense_System SHALL 自动停止录音
5. WHEN 录音停止, THE Defense_System SHALL 将录音内容发送到后端，由 STT_Service（Deepgram）转写为文本
6. IF 用户未授权麦克风权限, THEN THE Defense_System SHALL 提示用户"请允许麦克风权限以进行回答录音"
7. IF STT 转写失败, THEN THE Defense_System SHALL 提示用户"语音识别失败，请重试"并允许用户手动输入回答文本
8. THE Defense_System SHALL 将用户回答的文本存储到 Defense_Record 中

### Requirement 7: AI 反馈生成

**User Story:** As a 参赛团队用户, I want AI 根据项目全部上下文和我的回答生成简短反馈, so that 我能获得有针对性的评价。

#### Acceptance Criteria

1. WHEN 用户回答文本获取完成, THE AI_Feedback_Service SHALL 根据以下上下文生成反馈：Project_Profile、文本 PPT 内容、BP 内容、Predefined_Question 列表和用户回答文本
2. THE AI_Feedback_Service SHALL 生成 20 至 60 个中文字符的反馈文本
3. IF AI 生成的反馈少于 20 字或超过 60 字, THEN THE AI_Feedback_Service SHALL 重新生成或调整反馈以满足字数要求
4. THE Defense_System SHALL 将 AI 反馈文本存储到 Defense_Record 中
5. WHEN AI 反馈文本生成完成, THE Defense_System SHALL 通过 HeyGen_API 的 speak 接口让数字人评委朗读反馈内容
6. IF AI 反馈生成失败, THEN THE Defense_System SHALL 显示错误提示"AI反馈生成失败"并将错误状态记录到 Defense_Record

### Requirement 8: 问辩记录持久化与历史查看

**User Story:** As a 参赛团队用户, I want 查看之前所有问辩的提问、回答和反馈记录, so that 我可以回顾和改进我的回答。

#### Acceptance Criteria

1. THE Defense_System SHALL 在每次问辩完成后将完整的 Defense_Record（问题文本、用户回答文本、AI 反馈文本、问辩时间、回答时长设置）存储到 `defense_records` 数据库表
2. WHEN 用户进入数字人问辩页面, THE Defense_System SHALL 按时间倒序显示该项目的所有历史 Defense_Record
3. THE Defense_System SHALL 为每条历史记录显示：问辩时间、预定义问题列表、用户回答文本、AI 反馈文本
4. THE Defense_System SHALL 在 `defense_records` 表上启用 RLS 行级安全策略，确保用户只能查看自己项目的记录
5. IF 该项目没有历史 Defense_Record, THE Defense_System SHALL 显示"暂无问辩记录"的空状态提示

### Requirement 9: 问答时长配置

**User Story:** As a 参赛团队用户, I want 在问辩开始前自定义回答时长, so that 我可以根据问题复杂度调整回答时间。

#### Acceptance Criteria

1. THE Defense_System SHALL 在数字人问辩页面提供 Answer_Duration 输入框，默认值为 30 秒
2. THE Defense_System SHALL 限制 Answer_Duration 的取值范围为 10 秒至 120 秒
3. WHEN 用户修改 Answer_Duration 值, THE Defense_System SHALL 在本次问辩中使用用户设置的时长作为回答倒计时
4. IF 用户输入的 Answer_Duration 超出 10-120 秒范围, THEN THE Defense_System SHALL 自动修正为最近的有效值（10 或 120）

### Requirement 10: 数据库表设计

**User Story:** As a 开发者, I want 有清晰的数据库表结构支撑数字人问辩功能, so that 数据存储和查询高效可靠。

#### Acceptance Criteria

1. THE Defense_System SHALL 创建 `defense_questions` 表，包含字段：id (UUID), project_id (UUID, FK), content (TEXT, 最长 40 字), sort_order (INTEGER), created_at (TIMESTAMPTZ), updated_at (TIMESTAMPTZ)
2. THE Defense_System SHALL 创建 `defense_records` 表，包含字段：id (UUID), project_id (UUID, FK), user_id (UUID, FK), questions_snapshot (JSONB, 问辩时的问题快照), user_answer_text (TEXT), ai_feedback_text (TEXT), answer_duration (INTEGER, 秒), status (TEXT, 如 completed/failed), created_at (TIMESTAMPTZ)
3. THE Defense_System SHALL 在 `defense_questions` 表上启用 RLS，策略为：用户只能操作自己项目的问题
4. THE Defense_System SHALL 在 `defense_records` 表上启用 RLS，策略为：用户只能查看和创建自己项目的记录
5. THE Defense_System SHALL 为 `defense_questions.project_id` 和 `defense_records.project_id` 创建索引以优化查询性能

### Requirement 11: HeyGen API Key 配置管理

**User Story:** As a 开发者, I want HeyGen API Key 和 Avatar ID 通过环境变量管理, so that 敏感信息不硬编码在代码中。

#### Acceptance Criteria

1. THE Defense_System SHALL 在后端 config.py 中新增 `heygen_api_key` 和 `heygen_avatar_id` 配置项
2. THE Defense_System SHALL 从环境变量 `HEYGEN_API_KEY` 和 `HEYGEN_AVATAR_ID` 读取配置值
3. THE Defense_System SHALL 提供一个后端 API 端点，前端可通过该端点获取 HeyGen access token（由后端使用 API Key 生成），避免前端直接暴露 API Key
4. IF HEYGEN_API_KEY 未配置, THEN THE Defense_System SHALL 在启动时记录警告日志，并在用户尝试使用数字人问辩时返回"数字人服务未配置"错误
