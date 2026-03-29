# Implementation Plan: Defense Video Persistence

## Overview

实现数字人问辩视频持久化与异步生成功能。按照数据库→后端类型/Schema→服务层→路由→前端类型→前端组件的顺序递增实现，确保每一步都可验证。

## Tasks

- [x] 1. Database migration and backend schemas
  - [x] 1.1 Create database migration `backend/migrations/005_defense_video_persistence.sql`
    - Create `defense_video_tasks` table with columns: id, project_id, user_id, video_type, heygen_video_id, status, persistent_url, heygen_video_url, error_message, questions_hash, defense_record_id, created_at, updated_at
    - Add CHECK constraints for video_type ('question', 'feedback') and status ('pending', 'processing', 'completed', 'failed', 'outdated')
    - Create indexes on project_id and status (partial index for pending/processing)
    - Enable RLS with policy for project owners
    - ALTER `defense_records` table: add columns feedback_type (default 'text'), question_video_task_id, feedback_video_task_id
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Add Pydantic schemas in `backend/app/models/schemas.py`
    - Add `VideoTaskResponse` model (id, project_id, video_type, status, persistent_url, error_message, created_at, updated_at)
    - Add `GenerateQuestionVideoRequest` model (empty body, uses project questions)
    - Add `GenerateFeedbackVideoRequest` model (defense_record_id, feedback_text)
    - Extend `DefenseRecordResponse` with feedback_type, question_video_task_id, feedback_video_task_id
    - _Requirements: 1.1, 1.4, 5.2, 5.3_

  - [x] 1.3 Add backend settings in `backend/app/config.py`
    - Add `heygen_video_caption: bool = True`
    - Add `heygen_video_talking_style: str = "expressive"`
    - _Requirements: 9.3_

- [x] 2. Prompt templates and HeyGen service changes
  - [x] 2.1 Create prompt template files under `backend/prompts/templates/defense/`
    - Create `question_gen.md` with the question generation system prompt (extract from defense_service.py hardcoded QUESTION_GEN_SYSTEM_PROMPT)
    - Create `feedback_gen.md` with the feedback generation system prompt (extract from defense_service.py hardcoded FEEDBACK_SYSTEM_PROMPT)
    - Create `question_speech.md` with the speech text template containing `{{project_name}}`, `{{question_count}}`, `{{questions_text}}` placeholders
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 2.2 Add defense prompt loading to `backend/app/services/prompt_service.py`
    - Add `load_defense_template(name: str) -> str` method that loads from `defense/{name}.md`, falls back to hardcoded defaults if file missing
    - Ensure runtime loading (read file each call, no caching) so edits take effect without restart
    - _Requirements: 10.4, 10.5_

  - [ ]* 2.3 Write property test for prompt template loading (Property 13)
    - **Property 13: Prompt template runtime loading round-trip**
    - Test that existing files return file content, missing files return non-empty defaults, and modified files return new content on next load
    - **Validates: Requirements 10.4, 10.5**

  - [x] 2.4 Update `backend/app/services/avatar/heygen_video_service.py`
    - Add `caption` parameter to the video generation payload (from settings.heygen_video_caption)
    - Add `talking_style` parameter for talking_photo character type (from settings.heygen_video_talking_style)
    - _Requirements: 9.1, 9.2, 9.3_

  - [ ]* 2.5 Write property test for HeyGen payload configuration (Property 12)
    - **Property 12: HeyGen payload includes configured caption and talking_style**
    - Test that payload always includes caption from settings, and talking_photo type includes talking_style from settings
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [ ] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Video task service and background poller
  - [x] 4.1 Create `backend/app/services/video_task_service.py`
    - Implement `create_question_video_task(project_id, user_id, questions)`: assemble speech text via prompt template, call HeyGen generate, insert defense_video_tasks record with status "pending", return task dict
    - Implement `create_feedback_video_task(project_id, user_id, defense_record_id, feedback_text)`: call HeyGen generate, insert record, return task dict
    - Implement `get_task(task_id)`: query single task by ID
    - Implement `get_latest_question_task(project_id)`: get most recent question-type task for project
    - Implement `mark_outdated(project_id)`: update all completed question tasks for project to "outdated"
    - Implement `check_has_active_task(project_id)`: return True if any pending/processing task exists
    - Compute `questions_hash` as MD5 of sorted question contents for outdated detection
    - _Requirements: 1.1, 2.1, 3.2, 3.4, 3.5_

  - [ ]* 4.2 Write property test for video task creation (Property 1)
    - **Property 1: Video task creation preserves all required fields**
    - Test that created records contain exact project_id, video_type, heygen_video_id, and status "pending"
    - **Validates: Requirements 1.1, 2.1**

  - [ ]* 4.3 Write property test for question hash detection (Property 7)
    - **Property 7: Question hash change detection for outdated marking**
    - Test that different question sets produce different hashes, identical sets produce equal hashes
    - **Validates: Requirements 3.4**

  - [ ]* 4.4 Write property test for active task detection (Property 8)
    - **Property 8: Active task prevents duplicate generation**
    - Test that check_has_active_task returns True when pending/processing tasks exist
    - **Validates: Requirements 3.5**

  - [ ]* 4.5 Write property test for speech text formatting (Property 14)
    - **Property 14: Questions speech text formatting**
    - Test that formatted speech text contains project name, question count, and all question contents
    - **Validates: Requirements 3.2**

  - [x] 4.6 Create `backend/app/services/video_task_poller.py`
    - Implement `VideoTaskPoller` class with `start()`, `stop()`, `poll_once()` methods
    - `poll_once()`: query all pending/processing tasks, call HeyGen status API for each, handle completed (download video → upload to Supabase Storage → update persistent_url and status) and failed (update status and error_message)
    - Implement `_persist_video(task, video_url)`: download from HeyGen URL, upload to Supabase Storage `materials` bucket, return persistent_url
    - Add max poll attempts (720 = 1 hour), mark as failed with timeout error after exceeding
    - Individual task failures must not affect other tasks in the same cycle
    - _Requirements: 1.2, 1.3, 2.4_

  - [ ]* 4.7 Write property test for completed video persistence (Property 2)
    - **Property 2: Completed video persistence produces valid persistent URL**
    - Test that completed tasks get non-null persistent_url and status "completed" (mock download/upload)
    - **Validates: Requirements 1.2**

  - [ ]* 4.8 Write property test for failed task error recording (Property 3)
    - **Property 3: Failed video task records error information**
    - Test that failed tasks get status "failed" with non-empty error_message
    - **Validates: Requirements 1.3**

  - [x] 4.9 Register poller in FastAPI lifespan in `backend/app/main.py`
    - Create asyncio background task for VideoTaskPoller in startup event
    - Cancel task on shutdown
    - _Requirements: 2.4_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Defense service refactor and video task routes
  - [x] 6.1 Refactor `backend/app/services/defense_service.py`
    - Replace hardcoded QUESTION_GEN_SYSTEM_PROMPT and FEEDBACK_SYSTEM_PROMPT with PromptService file loading
    - Replace hardcoded `format_questions_speech` with prompt template loading from `question_speech.md`
    - Add `feedback_type` parameter to `submit_answer` method
    - Extend `_insert_record` to include feedback_type, question_video_task_id, feedback_video_task_id
    - Call `video_task_service.mark_outdated()` after question create/update/delete operations
    - _Requirements: 1.4, 5.2, 5.3, 10.4, 10.5, 3.4_

  - [ ]* 6.2 Write property test for feedback type consistency (Property 4)
    - **Property 4: Defense record feedback type consistency**
    - Test that feedback_type "text" ↔ feedback_video_task_id is null, feedback_type "video" ↔ feedback_video_task_id is non-null
    - **Validates: Requirements 1.4, 5.2, 5.3**

  - [x] 6.3 Add video task routes to `backend/app/routes/defense.py`
    - POST `/defense/video-tasks/generate-question`: create question video task, return 409 if active task exists
    - POST `/defense/video-tasks/generate-feedback`: create feedback video task with defense_record_id and feedback_text
    - GET `/defense/video-tasks/{task_id}`: return task status, persistent_url, progress
    - GET `/defense/video-tasks/latest-question`: return latest question task for project
    - _Requirements: 2.1, 2.3, 3.2, 5.3_

  - [ ]* 6.4 Write property test for polling endpoint state (Property 5)
    - **Property 5: Polling endpoint returns correct task state**
    - Test that endpoint returns current status and non-null persistent_url when completed
    - **Validates: Requirements 2.3**

- [ ] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Frontend types and API client
  - [x] 8.1 Add TypeScript types in `frontend/src/types/index.ts`
    - Add `VideoTask` interface (id, project_id, video_type, status, persistent_url, error_message, created_at, updated_at)
    - Extend `DefenseRecord` interface with feedback_type, question_video_task_id, feedback_video_task_id
    - _Requirements: 1.1, 1.4_

  - [x] 8.2 Add API methods to `frontend/src/services/api.ts` defenseApi
    - Add `generateQuestionVideo(projectId)`: POST to `/defense/video-tasks/generate-question`
    - Add `generateFeedbackVideo(projectId, defenseRecordId, feedbackText)`: POST to `/defense/video-tasks/generate-feedback`
    - Add `getVideoTask(projectId, taskId)`: GET `/defense/video-tasks/{taskId}`
    - Add `getLatestQuestionTask(projectId)`: GET `/defense/video-tasks/latest-question`
    - _Requirements: 2.1, 2.3, 3.2, 5.3_

- [x] 9. Frontend components and page changes
  - [x] 9.1 Create `QuestionPanel` component in `frontend/src/components/QuestionPanel.tsx`
    - Display defense questions with sequence numbers ("问题1", "问题2", etc.)
    - Responsive: side panel on wide screens, below video on narrow screens
    - Show during "speaking" and "recording" phases
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 9.2 Write property test for question panel rendering (Property 11)
    - **Property 11: Question panel displays all questions with sequence numbers**
    - Use fast-check to test that all questions render with correct sequence numbers and content
    - **Validates: Requirements 8.1, 8.2**

  - [x] 9.3 Create `FeedbackTypeModal` component in `frontend/src/components/FeedbackTypeModal.tsx`
    - Modal dialog with two options: "文本反馈" and "视频反馈"
    - Shown after answer recording completes and AI feedback text is generated
    - Returns selected feedback_type to parent
    - _Requirements: 5.1_

  - [x] 9.4 Create `VideoTaskStatus` component in `frontend/src/components/VideoTaskStatus.tsx`
    - Display status tags: red "视频生成失败" for failed, blue "生成中" with spinner for pending/processing, "视频不可用" warning for null persistent_url
    - Show progress bar during generation
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ]* 9.5 Write property test for status tag rendering (Property 9)
    - **Property 9: Video task status tag rendering**
    - Use fast-check to test correct tag color and text for each status value
    - **Validates: Requirements 6.1, 6.2, 6.3**

  - [x] 9.6 Update `frontend/src/pages/DigitalDefense.tsx` - pre-generate and async flow
    - Add "生成提问视频" button: visible when questions exist and provider is "heygen", disabled when active task exists
    - On click: call `generateQuestionVideo`, start polling `getVideoTask` at 5s intervals
    - When task completes: show "开始数字人问辩" and "放弃此次问辩" buttons
    - On "开始数字人问辩": play question video from persistent_url, then transition to recording
    - On "放弃此次问辩": return to idle without creating a record
    - Integrate `QuestionPanel` next to video area during speaking/recording phases
    - On page mount: check for existing pending/processing tasks via `getLatestQuestionTask` and resume polling
    - _Requirements: 2.1, 2.2, 3.1, 3.3, 3.5, 4.1, 4.2, 4.3, 8.1_

  - [ ]* 9.7 Write property test for pre-generate button visibility (Property 6)
    - **Property 6: Pre-generate button visibility logic**
    - Use fast-check to test button visible iff questionCount > 0 AND provider is "heygen"
    - **Validates: Requirements 3.1**

  - [x] 9.8 Update `frontend/src/pages/DigitalDefense.tsx` - feedback type selection and history
    - After recording + AI feedback generation: show `FeedbackTypeModal`
    - "文本反馈": display text, save record with feedback_type "text"
    - "视频反馈": call `generateFeedbackVideo`, poll, play video, save record with feedback_type "video"
    - Update history record list: add video playback buttons ("播放提问视频", "播放反馈视频") when persistent_url exists
    - Add inline video player for playback within record entries
    - Show `VideoTaskStatus` tags in history list for each record's associated video tasks
    - Handle expired URLs: show "视频链接已失效" and hide playback button on error
    - _Requirements: 5.1, 5.2, 5.3, 6.1, 6.2, 6.3, 7.1, 7.2, 7.3, 7.4_

  - [ ]* 9.9 Write property test for playback button visibility (Property 10)
    - **Property 10: Video playback button visibility**
    - Use fast-check to test playback button shown iff persistent_url is non-null and non-empty
    - **Validates: Requirements 7.1, 7.2**

- [x] 10. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Backend uses Python (FastAPI + Pydantic + Supabase), frontend uses TypeScript (React 19 + Ant Design)
- Property tests use Hypothesis (Python) and fast-check (TypeScript)
- All HeyGen API calls and Supabase operations should be mocked in tests
- Checkpoints ensure incremental validation at each major milestone
