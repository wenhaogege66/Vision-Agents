# Requirements Document

## Introduction

增强数字人问辩（Digital Human Defense）功能，实现 HeyGen 视频的持久化保存与异步生成。当前系统中 HeyGen 生成的评委提问视频和反馈视频为临时播放后即丢弃，且视频生成过程阻塞用户操作。本需求旨在：将视频 ID 及 URL 持久化到数据库，支持历史回放；引入异步生成机制，允许用户在视频渲染期间离开页面；支持用户手动提前为项目预生成提问视频；在回答完成后让用户选择文本反馈或视频反馈形式；对视频生成失败或为空的记录进行标记显示；在问辩过程中显示题目供用户参考；以及为生成的视频配置字幕和合适的动作模型。

## Glossary

- **Defense_System**: 数字人问辩系统，负责评委提问视频生成、用户回答录制、AI 反馈生成与展示的完整流程
- **Video_Task**: 视频生成任务记录，存储 HeyGen video_id、生成状态、视频类型、持久化 URL 等信息
- **Question_Video**: 评委提问视频，由 HeyGen 根据预定义问题文本生成的数字人视频
- **Feedback_Video**: 评委反馈视频，由 HeyGen 根据 AI 反馈文本生成的数字人视频
- **Persistent_URL**: 将 HeyGen 返回的临时 video_url（7天过期）下载后上传至 Supabase Storage 获得的长期有效 URL
- **Defense_Record**: 问辩记录，存储一次完整问辩的问题快照、用户回答、AI 反馈及关联视频信息
- **HeyGen_API**: HeyGen 视频生成 API，通过 POST /v2/video/generate 提交生成请求，通过 GET /v1/video_status.get 轮询状态
- **Feedback_Type**: 反馈类型，用户在回答完成后选择的反馈展示方式，包含"文本反馈"和"视频反馈"两种

## Requirements

### Requirement 1: 视频生成任务持久化

**User Story:** As a 用户, I want 每次 HeyGen 视频生成请求都被记录到数据库, so that 视频生成状态可被追踪，生成完成后的视频可被回放。

#### Acceptance Criteria

1. WHEN a Question_Video or Feedback_Video generation request is submitted to HeyGen_API, THE Defense_System SHALL create a Video_Task record containing the HeyGen video_id, video type ("question" or "feedback"), associated project_id, and initial status "pending".
2. WHEN HeyGen_API returns a "completed" status with a video_url for a Video_Task, THE Defense_System SHALL download the video file from the video_url and upload the video file to Supabase Storage, then update the Video_Task record with the Persistent_URL and status "completed".
3. WHEN HeyGen_API returns a "failed" status for a Video_Task, THE Defense_System SHALL update the Video_Task record status to "failed" and store the error message.
4. THE Defense_System SHALL associate each Defense_Record with the corresponding Question_Video Video_Task ID and Feedback_Video Video_Task ID (nullable).

### Requirement 2: 异步视频生成

**User Story:** As a 用户, I want 点击"开始问辩"后视频在后台异步生成, so that 我可以离开页面做其他事情，回来时继续查看生成进度。

#### Acceptance Criteria

1. WHEN a user clicks "开始问辩", THE Defense_System SHALL submit the video generation request to HeyGen_API, create a Video_Task record, and return the Video_Task ID to the frontend without blocking the user interface.
2. WHEN a user navigates away from the defense page and returns while a Video_Task status is "pending" or "processing", THE Defense_System SHALL display the current generation progress status for the Video_Task.
3. THE Defense_System SHALL provide a polling endpoint that returns the current status, progress percentage, and Persistent_URL (when available) for a given Video_Task.
4. WHILE a Video_Task status is "pending" or "processing", THE Defense_System SHALL poll HeyGen_API at 5-second intervals via a backend background task to update the Video_Task status.

### Requirement 3: 手动预生成提问视频

**User Story:** As a 用户, I want 在数字人问辩页面或项目仪表盘手动点击按钮预生成评委提问视频, so that 正式问辩时无需等待视频渲染。

#### Acceptance Criteria

1. THE Defense_System SHALL provide a "生成提问视频" button on the defense page AND on the project dashboard page, visible when at least one defense question exists and the avatar provider is "heygen".
2. WHEN a user clicks "生成提问视频", THE Defense_System SHALL submit a Question_Video generation request to HeyGen_API using the current defense questions and create a Video_Task record. This SHALL only be triggered by explicit user action, NOT automatically.
3. WHEN a pre-generated Question_Video Video_Task has status "completed", THE Defense_System SHALL display the video as ready and allow the user to proceed to defense without re-generating.
4. WHEN defense questions are modified after a Question_Video has been pre-generated, THE Defense_System SHALL mark the existing pre-generated Video_Task as "outdated" and display a prompt to regenerate.
5. THE "生成提问视频" button SHALL be disabled when a Video_Task for the same project is already in "pending" or "processing" status.

### Requirement 4: 问辩流程交互优化

**User Story:** As a 用户, I want 提问视频生成完成后选择开始问辩或放弃, so that 我可以在准备好后再开始回答。

#### Acceptance Criteria

1. WHEN a Question_Video Video_Task reaches status "completed", THE Defense_System SHALL display two action buttons: "开始数字人问辩" and "放弃此次问辩".
2. WHEN a user clicks "开始数字人问辩", THE Defense_System SHALL play the Question_Video and then transition to the recording phase.
3. WHEN a user clicks "放弃此次问辩", THE Defense_System SHALL return to the idle state without creating a Defense_Record.

### Requirement 5: 反馈类型选择

**User Story:** As a 用户, I want 回答完成后选择文本反馈或视频反馈, so that 我可以根据需要选择快速查看文字或观看数字人视频反馈。

#### Acceptance Criteria

1. WHEN a user finishes recording an answer and the AI feedback text is generated, THE Defense_System SHALL display a modal dialog with two options: "文本反馈" and "视频反馈".
2. WHEN a user selects "文本反馈", THE Defense_System SHALL display the AI feedback text directly on the page and save the Defense_Record with feedback_type "text" and no Feedback_Video.
3. WHEN a user selects "视频反馈", THE Defense_System SHALL submit a Feedback_Video generation request to HeyGen_API, display the generation progress, play the video upon completion, and save the Defense_Record with feedback_type "video" and the associated Feedback_Video Video_Task ID.

### Requirement 6: 视频生成失败标记

**User Story:** As a 用户, I want 视频生成失败或为空的记录被明确标记, so that 我能区分正常记录和异常记录。

#### Acceptance Criteria

1. WHEN a Video_Task status is "failed", THE Defense_System SHALL display a red "视频生成失败" tag next to the corresponding record in the history list.
2. WHEN a Defense_Record has an associated Video_Task with a null or empty Persistent_URL, THE Defense_System SHALL display a warning indicator and the text "视频不可用" in the history list.
3. WHEN a Video_Task status is "pending" or "processing", THE Defense_System SHALL display a blue "生成中" tag with a loading indicator in the history list.

### Requirement 7: 历史记录视频回放

**User Story:** As a 用户, I want 在历史问辩记录中回放当时的评委提问视频和反馈视频, so that 我可以回顾完整的问辩过程。

#### Acceptance Criteria

1. WHEN a Defense_Record has an associated Question_Video with a valid Persistent_URL, THE Defense_System SHALL display a "播放提问视频" button in the history record entry.
2. WHEN a Defense_Record has an associated Feedback_Video with a valid Persistent_URL, THE Defense_System SHALL display a "播放反馈视频" button in the history record entry.
3. WHEN a user clicks a video playback button, THE Defense_System SHALL open an inline video player within the record entry and play the video from the Persistent_URL.
4. IF a Persistent_URL is expired or inaccessible, THEN THE Defense_System SHALL display an error message "视频链接已失效" and hide the playback button.

### Requirement 8: 问辩过程中题目显示

**User Story:** As a 用户, I want 在数字人问辩过程中数字人视频旁边显示当前的评委问题列表, so that 我在回答时可以随时参考题目内容。

#### Acceptance Criteria

1. WHEN the defense is in the "speaking" (提问视频播放) or "recording" (用户回答) phase, THE Defense_System SHALL display a side panel next to the avatar video area showing the full list of defense questions.
2. THE question display panel SHALL show each question with its sequence number (e.g., "问题1", "问题2") and content text.
3. THE question display panel SHALL be responsive: on wide screens it appears as a side panel beside the video, on narrow screens it appears below the video.

### Requirement 9: 视频字幕与动作模型配置

**User Story:** As a 用户, I want HeyGen 生成的视频带有字幕并使用合适的动作模型, so that 视频内容更易理解且数字人表现更自然。

#### Acceptance Criteria

1. WHEN submitting a video generation request to HeyGen_API, THE Defense_System SHALL include the caption parameter set to true to enable subtitle generation in the video.
2. WHEN submitting a video generation request to HeyGen_API using a talking_photo character type, THE Defense_System SHALL include the talking_style parameter set to "expressive" to enable natural head and body movements.
3. THE video generation configuration (caption, talking_style) SHALL be configurable via backend settings without requiring code changes.

### Requirement 10: 数字人 Prompt 模板统一管理

**User Story:** As a 开发者, I want 数字人问辩相关的所有 AI prompt（问题生成、反馈生成、提问话术）统一存放在 backend/prompts/templates/ 目录下, so that prompt 内容可以独立于代码进行维护和迭代。

#### Acceptance Criteria

1. THE Defense_System SHALL store the question generation system prompt in `backend/prompts/templates/defense/question_gen.md`.
2. THE Defense_System SHALL store the feedback generation system prompt in `backend/prompts/templates/defense/feedback_gen.md`.
3. THE Defense_System SHALL store the question speech text template in `backend/prompts/templates/defense/question_speech.md`.
4. THE Defense_System SHALL load these prompt templates from the file system at runtime, falling back to hardcoded defaults if the file does not exist.
5. WHEN a prompt template file is modified, THE Defense_System SHALL use the updated content on the next API call without requiring a server restart.
