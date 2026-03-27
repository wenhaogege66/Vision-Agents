---
inclusion: manual
---

# 数字人服务架构参考

## 概述

数字人问辩功能支持两种数字人服务提供商，通过抽象层统一接口：

- **LiveAvatar**（实时流式）：基于 WebRTC 的实时数字人，延迟低，交互自然
- **HeyGen**（视频生成）：生成高质量数字人视频，需等待渲染

## 架构

```
backend/app/services/avatar/
├── base.py                    # 抽象基类
├── liveavatar_service.py      # LiveAvatar FULL 模式实现
└── heygen_video_service.py    # HeyGen v2/video/generate 实现
```

## LiveAvatar API 参考

- 文档：https://docs.liveavatar.com
- SDK：`@heygen/liveavatar-web-sdk`
- API 基础 URL：`https://api.liveavatar.com`
- 创建会话：`POST /v1/sessions/token`
- 模式：FULL（托管 ASR/LLM/TTS）、LITE（自定义管线）、CUSTOM（自定义 LiveKit）

### 创建会话 Token

```json
POST https://api.liveavatar.com/v1/sessions/token
Headers: x-api-key: <LIVEAVATAR_API_KEY>

{
  "mode": "FULL",
  "avatar_id": "<avatar_id>",
  "avatar_persona": { "language": "zh" }
}

Response: { "data": { "session_id": "...", "session_token": "..." } }
```

### 前端 SDK 使用

```typescript
import { LiveAvatarSession, SessionEvent, SessionState } from '@heygen/liveavatar-web-sdk';

const session = new LiveAvatarSession(sessionToken, { voiceChat: true });
session.on(SessionEvent.SESSION_STREAM_READY, () => session.attach(videoElement));
await session.start();
// ... 交互 ...
await session.stop();
```

## HeyGen Video API 参考

- 文档：https://docs.heygen.com
- 生成视频：`POST https://api.heygen.com/v2/video/generate`
- 查询状态：`GET https://api.heygen.com/v1/video_status.get?video_id=<id>`

### 生成视频

```json
POST https://api.heygen.com/v2/video/generate
Headers: X-Api-Key: <HEYGEN_API_KEY>

{
  "video_inputs": [{
    "character": { "type": "avatar", "avatar_id": "...", "avatar_style": "normal" },
    "voice": { "type": "text", "input_text": "...", "voice_id": "zh-CN-XiaoxiaoNeural" }
  }]
}

Response: { "data": { "video_id": "..." } }
```

### 查询状态

```
GET https://api.heygen.com/v1/video_status.get?video_id=<id>
Response: { "data": { "status": "completed", "video_url": "..." } }
```

## 环境变量

```
HEYGEN_API_KEY=...
HEYGEN_AVATAR_ID=80d4afa941c243beb0a1116c95ea48ee
LIVEAVATAR_API_KEY=...
LIVEAVATAR_AVATAR_ID=...
```
