# 需求文档：HeyGen 模式优化

## 简介

对数字人问辩系统中的 HeyGen 模式进行全面重新设计和优化。主要包括：区分 Photo Avatar 与 Digital Twin 两种数字人类型、分类展示用户自有和公共资源、根据 Avatar 类型差异化处理视频生成参数、丰富视频生成自定义选项（含强制字幕）、利用多场景能力在视频中展示问题文字、完善视频复用机制以节省 API 配额、以及提供 Photo Avatar 创建功能。同时将 API 升级到新版，并更新默认 Avatar 和音色为用户的 Digital Twin。

## 术语表

- **HeyGen_Service**: 后端 HeyGen 视频生成服务模块（`heygen_video_service.py`），负责调用 HeyGen API 生成数字人视频、查询状态、列出资源
- **Avatar_API**: HeyGen 官方 Avatar 相关 REST API（`/v2/avatars`、`/v2/photo_avatar/*`）
- **Voice_API**: HeyGen 官方语音相关 REST API（`/v2/voices`）
- **Video_API**: HeyGen 官方视频生成 REST API（新版 `POST /v2/videos`）
- **Studio_API**: HeyGen Studio 视频生成 REST API（`POST /v2/video/generate`），支持多场景（video_inputs 数组，1-50 个场景）、自定义背景、字幕等高级功能
- **Photo_Avatar**: 通过上传照片生成的静态数字人形象，支持 motion_prompt 和 expressiveness 参数
- **Digital_Twin**: 通过在 HeyGen 官网录制视频和声音训练生成的高保真数字人分身，API 中 avatar_type 为 `video_avatar`
- **Defense_Frontend**: 前端数字人问辩页面（`DigitalDefense.tsx`），提供数字人选择、视频生成、问辩交互等 UI
- **Video_Task_Service**: 后端视频任务管理服务（`video_task_service.py`），负责创建和管理视频生成任务
- **Motion_Prompt**: 仅 Photo_Avatar 支持的动作描述提示词，用于控制数字人在视频中的肢体动作和表情
- **Defense_Route**: 后端问辩路由模块（`defense.py`），提供数字人资源列表、视频生成等 API 端点

## 需求

### 需求 1：区分 Photo Avatar 和 Digital Twin

**用户故事：** 作为开发者，我希望系统能正确区分 Photo Avatar 和 Digital Twin 两种数字人类型，以便根据类型差异化处理视频生成参数。

#### 验收标准

1. WHEN HeyGen_Service 调用 Avatar_API 获取数字人列表时，THE HeyGen_Service SHALL 根据 API 返回的 `avatar_type` 字段将数字人分类为 `photo_avatar` 或 `digital_twin`（对应 API 中的 `video_avatar` 类型）
2. THE HeyGen_Service SHALL 在返回的数字人数据中包含 `avatar_type` 字段，取值为 `photo_avatar` 或 `digital_twin`
3. THE HeyGen_Service SHALL 移除当前基于 ID 格式（32位 hex）判断 `talking_photo` 类型的逻辑，改为使用 API 返回的类型信息
4. THE Settings SHALL 将 `heygen_video_avatar_id` 的默认值更新为 `8d4aa85254354488a0f9bce7b4c3549e`（用户的 Digital Twin）
5. THE Settings SHALL 将 `heygen_video_voice_id` 的默认值更新为 `769716d5135541db93e95ce84508c59e`（用户的"文豪本音"音色）

### 需求 2：分类展示数字人和音色

**用户故事：** 作为用户，我希望在 HeyGen 模式下选择数字人和音色时，能看到分类展示（"我的"和"公共"），以便快速找到自己的资源。

#### 验收标准

1. WHEN Defense_Frontend 展示数字人选择器时，THE Defense_Frontend SHALL 使用分组下拉菜单，将数字人分为"我的"和"公共"两个分组
2. WHEN Defense_Frontend 展示"我的"分组时，THE Defense_Frontend SHALL 在每个数字人条目中显示其类型标签（Photo Avatar 或 Digital Twin）
3. WHEN Defense_Frontend 展示音色选择器时，THE Defense_Frontend SHALL 使用分组下拉菜单，将音色分为"我的"和"公共"两个分组
4. THE HeyGen_Service SHALL 在返回的数字人列表数据中包含 `is_custom` 字段，标识该数字人是否为用户自有资源
5. THE Defense_Frontend SHALL 将"我的"分组显示在"公共"分组之前

### 需求 3：根据 Avatar 类型差异化处理视频生成

**用户故事：** 作为开发者，我希望系统根据所选 Avatar 的类型（Photo Avatar 或 Digital Twin）自动调整视频生成参数，以充分利用各类型的特性。

#### 验收标准

1. WHEN 用户选择的 Avatar 类型为 Photo_Avatar 时，THE HeyGen_Service SHALL 在视频生成请求中包含 `motion_prompt` 字段
2. WHEN 用户选择的 Avatar 类型为 Photo_Avatar 时，THE HeyGen_Service SHALL 在视频生成请求中包含 `expressiveness` 字段
3. THE HeyGen_Service SHALL 从 `backend/prompts/templates/defense/` 目录下的模板文件加载 Motion_Prompt 内容
4. WHEN 用户选择的 Avatar 类型为 Digital_Twin 时，THE HeyGen_Service SHALL 在视频生成请求中省略 `motion_prompt` 和 `expressiveness` 字段
5. THE HeyGen_Service SHALL 将视频生成 API 从旧版 `v2/video/generate` 升级到新版 `POST /v2/videos`，按照新 API 的请求格式构建 payload

### 需求 4：丰富视频生成选项

**用户故事：** 作为用户，我希望在生成数字人视频时能自定义更多选项（如语种、分辨率、宽高比等），以获得更符合需求的视频效果。

#### 验收标准

1. THE Defense_Frontend SHALL 提供语音语种选择控件，默认值为中文（`zh-CN`）
2. THE Defense_Frontend SHALL 提供分辨率选择控件，支持 `1080p` 和 `720p` 两个选项，默认值为 `720p`
3. THE Defense_Frontend SHALL 提供宽高比选择控件，支持 `16:9` 和 `9:16` 两个选项，默认值为 `16:9`
4. WHEN 用户选择的 Avatar 类型为 Photo_Avatar 时，THE Defense_Frontend SHALL 显示表情丰富度选择控件，支持 `low`、`medium`、`high` 三个选项，默认值为 `medium`
5. THE Defense_Frontend SHALL 提供背景移除开关控件，默认值为关闭
6. THE HeyGen_Service SHALL 在所有视频生成请求中始终开启字幕（`caption: true`），无论 Avatar 类型是 Photo_Avatar 还是 Digital_Twin，确保生成的视频包含字幕
7. THE Defense_Route SHALL 接收前端传递的视频生成选项参数（语种、分辨率、宽高比、表情丰富度、背景移除）
8. THE HeyGen_Service SHALL 将用户选择的视频生成选项正确映射到 Video_API 请求参数中（`caption`、`resolution`、`aspect_ratio`、`expressiveness`、`remove_background`、`voice_settings.locale`）

### 需求 5：多场景视频生成与问题文字展示

**用户故事：** 作为用户，我希望数字人提问视频中每个问题都能以文字形式直观展示在画面上，以便我更清晰地理解和记忆评委的问题。

#### 验收标准

1. THE Video_Task_Service SHALL 将多个问题拆分为多个独立场景（scenes），每个场景对应一个问题，利用 Studio API 的 `video_inputs` 数组（支持 1-50 个场景）生成一段连贯的视频
2. THE HeyGen_Service SHALL 为每个问题场景生成一张包含问题序号和问题文字的背景图片，并将其作为该场景的 `background`（类型为 `image`）
3. THE HeyGen_Service SHALL 使用 Python 图像库（如 Pillow）在后端动态生成问题背景图片，图片包含：问题序号（如"问题 1"）、问题文字内容、统一的视觉风格（配色、字体大小、布局）
4. THE HeyGen_Service SHALL 在每个场景的 `character` 配置中设置 `scale` 和 `position` 参数，将数字人缩小并偏移到画面一侧（如左侧），为问题文字留出展示空间
5. THE HeyGen_Service SHALL 通过 HeyGen Asset API（`POST /v2/asset`）上传生成的背景图片，获取 `image_asset_id` 用于视频生成请求
6. THE Video_Task_Service SHALL 在第一个场景中包含开场白（如"你好，我是数字人评委，对于你们的 XX 项目，我有以下 N 个问题"），该场景使用纯色或默认背景
7. THE HeyGen_Service SHALL 确保多场景视频生成后各场景自然衔接，形成一段完整的提问视频

### 需求 6：Photo Avatar 创建功能

**用户故事：** 作为用户，我希望能在系统内直接创建 Photo Avatar，以便快速获得自定义数字人形象。

#### 验收标准

1. THE Defense_Frontend SHALL 在数字人选择区域提供"创建 Photo Avatar"按钮
2. WHEN 用户点击"创建 Photo Avatar"按钮时，THE Defense_Frontend SHALL 弹出创建表单，收集以下必填信息：名称、年龄段（Young Adult / Early Middle Age / Late Middle Age / Senior / Unspecified）、性别（Woman / Man / Unspecified）、种族、朝向（square / horizontal / vertical）、姿势（half_body / close_up / full_body）、风格（Realistic / Pixar / Cinematic / Vintage / Noir / Cyberpunk / Unspecified）、外观描述文本（最长 1000 字符）
3. THE Defense_Route SHALL 提供 `POST` 端点接收 Photo Avatar 创建请求，并调用 HeyGen_Service 转发至 Avatar_API
4. THE HeyGen_Service SHALL 调用 `POST /v2/photo_avatar/photo/generate` 创建 Photo Avatar，并返回 `generation_id`
5. THE Defense_Frontend SHALL 在创建表单中显示提示信息："如需效果更好的 Digital Twin，请前往 HeyGen 官网创建"
6. WHEN Photo Avatar 创建请求提交成功后，THE Defense_Frontend SHALL 显示创建状态，并提供查询创建进度的功能
7. THE HeyGen_Service SHALL 提供查询 Photo Avatar 创建状态的方法，调用 `GET /v2/photo_avatar/photo/{generation_id}`

### 需求 7：视频复用机制与数据库优化

**用户故事：** 作为用户，我希望当问题内容和视频生成选项（数字人、音色、分辨率等）均未变化时，系统能直接复用已生成的视频而无需重新生成，以节省 HeyGen API 配额消耗和等待时间。

#### 验收标准

1. THE Video_Task_Service SHALL 计算 `config_hash` 时将所有影响视频内容的参数纳入哈希计算，包括：问题内容列表、avatar_id、voice_id、avatar_type、resolution、aspect_ratio、expressiveness、remove_background、voice_locale
2. WHEN 存在相同 `config_hash` 且状态为 `completed` 的视频任务时，THE Video_Task_Service SHALL 直接返回已有视频任务记录，跳过 HeyGen API 调用
3. THE Database SHALL 在 `defense_video_tasks` 表中新增以下列：`config_hash TEXT`（用于视频复用匹配）、`avatar_type TEXT`（记录生成时的数字人类型）、`video_options JSONB DEFAULT '{}'`（存储完整的视频生成选项快照）
4. THE Database SHALL 为 `config_hash` 列创建条件索引（`WHERE status = 'completed'`），加速复用查询
5. WHEN 视频被复用时，THE Defense_Route SHALL 在响应中包含标识字段（如 `is_reused: true`），以便前端区分
6. WHEN 视频被复用时，THE Defense_Frontend SHALL 显示明确的提示信息（如"复用已有视频，无需重新生成"），让用户知晓当前视频是复用的而非新生成的
7. WHEN 视频是新生成的且生成完成后，THE Defense_Frontend SHALL 显示正常的生成完成提示，不显示复用标识

### 需求 8：视频生成请求模型更新

**用户故事：** 作为开发者，我希望后端请求模型能支持所有新增的视频生成参数，以便前后端数据传递完整。

#### 验收标准

1. THE Schemas SHALL 定义新的视频生成请求模型，包含以下可选字段：`avatar_id`、`voice_id`、`resolution`（默认 `1080p`）、`aspect_ratio`（默认 `16:9`）、`expressiveness`（默认 `medium`）、`remove_background`（默认 `false`）、`voice_locale`（默认 `zh-CN`）
2. THE Schemas SHALL 定义 Photo Avatar 创建请求模型，包含所有必填字段：`name`、`age`、`gender`、`ethnicity`、`orientation`、`pose`、`style`、`appearance`
3. THE Schemas SHALL 定义 Photo Avatar 创建状态响应模型，包含 `generation_id`、`status` 字段
