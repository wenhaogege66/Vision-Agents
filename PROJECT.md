# AI 评委系统 — 项目全景文档

> 本文档由 Kiro 维护，记录项目的产品构想、技术架构、功能现状与演进方向。
> 每次产品需求或架构发生变化时同步更新。

---

## 1. 产品定位

**中国大学生创新大赛 AI 评委系统** — 基于多模态 AI 的智能评审与路演模拟平台。

面向参赛团队，提供：
- 文本材料的 AI 自动评审（BP、PPT 等）
- 路演视频的离线 AI 评审（视觉 + 演讲者表现）
- 现场路演模拟（AI 评委通过 WebRTC 实时音视频互动）

核心价值：让参赛团队在正式比赛前获得接近真实评委水平的反馈，反复打磨项目。

---

## 2. 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | React 19 + TypeScript + Vite 8 + Ant Design 6 |
| 后端 | FastAPI + Python 3.13 |
| 数据库 | Supabase（PostgreSQL + Auth + Storage） |
| AI 框架 | [Vision-Agents](https://github.com/GetStream/Vision-Agents) + Qwen Realtime（通义千问多模态） |
| 音视频 | GetStream WebRTC + Stream Video React SDK |
| 语音识别 | Deepgram STT |
| 包管理 | 后端 `uv`，前端 `npm` |
| 部署 | Docker Compose（backend + frontend/nginx） |

---

## 3. 项目结构

```
.
├── docker-compose.yml          # 容器编排
├── start.sh                    # 一键启动脚本（dev / docker）
├── mock/                       # 测试用模拟材料（量子云桥示例项目）
│
├── backend/
│   ├── pyproject.toml          # Python 依赖（uv 管理）
│   ├── uv.lock                 # uv 锁文件
│   ├── Dockerfile              # Python 3.12-slim + uv
│   ├── .env / .env.example     # 环境变量
│   ├── migrations/             # Supabase SQL 迁移脚本
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_experience_enhancement.sql
│   │   └── 003_system_optimization_v2.sql
│   ├── rules/                  # 评审规则文件（按赛事/赛道/组别组织）
│   │   └── guochuangsai/       # 国创赛
│   │       ├── gaojiao/        # 高教赛道（本科创业/创意、研究生创业/创意）
│   │       ├── chanye/         # 产业赛道
│   │       ├── honglv/         # 红旅赛道
│   │       ├── mengya/         # 萌芽赛道
│   │       └── zhijiao/        # 职教赛道
│   ├── knowledge/              # 评委经验知识库
│   │   ├── bp/                 # BP 评审经验
│   │   ├── text_ppt/           # 文本 PPT 评审经验
│   │   ├── presentation_ppt/   # 路演 PPT 评审经验
│   │   └── presentation/       # 路演评审经验
│   ├── prompts/                # Prompt 模板
│   │   ├── templates/          # 各场景 prompt（text_review / offline_review / live / ppt_visual）
│   │   └── styles/             # 评委风格（strict / gentle / academic）
│   └── app/
│       ├── main.py             # FastAPI 入口
│       ├── config.py           # pydantic-settings 配置
│       ├── models/
│       │   ├── database.py     # Supabase 客户端初始化
│       │   └── schemas.py      # Pydantic 请求/响应模型
│       ├── routes/             # API 路由
│       │   ├── auth.py
│       │   ├── competitions.py
│       │   ├── projects.py
│       │   ├── materials.py
│       │   ├── reviews.py
│       │   ├── live_presentation.py
│       │   ├── judge_styles.py
│       │   ├── voices.py
│       │   └── tags.py
│       ├── services/           # 业务逻辑
│       │   ├── auth_service.py
│       │   ├── project_service.py
│       │   ├── material_service.py
│       │   ├── text_review_service.py
│       │   ├── offline_review_service.py
│       │   ├── live_presentation_service.py   # Vision-Agents AI 评委
│       │   ├── export_service.py              # PDF 导出
│       │   ├── voice_service.py               # 音色管理
│       │   ├── stt_service.py                 # Deepgram 语音转文字
│       │   ├── profile_service.py             # AI 项目简介提取
│       │   ├── prompt_service.py              # 动态 prompt 组装
│       │   ├── rule_service.py                # 评审规则加载
│       │   ├── knowledge_service.py           # 知识库加载
│       │   └── tag_service.py                 # 自定义标签
│       └── utils/              # 工具模块
│           ├── ai_utils.py             # 通义千问 API 调用
│           ├── dashscope_file.py        # DashScope 文件上传
│           ├── dashscope_upload.py
│           ├── file_utils.py            # 文件处理（PPT→图片等）
│           ├── storage_utils.py         # Supabase Storage 操作
│           ├── timing_middleware.py      # API 耗时监控中间件
│           └── timing.py               # 计时上下文管理器
│
└── frontend/
    ├── package.json
    ├── vite.config.ts          # Vite 配置 + /api 代理
    ├── Dockerfile              # Node 20 构建 + nginx 部署
    ├── nginx.conf              # 反向代理 /api → backend:8000
    └── src/
        ├── App.tsx             # 路由定义
        ├── types/index.ts      # TypeScript 类型（对应后端 schemas）
        ├── services/api.ts     # Axios 实例 + 拦截器 + 重试机制
        ├── contexts/           # AuthContext 全局认证状态
        ├── hooks/              # 自定义 hooks
        │   ├── useConcurrentState.ts    # 并发状态管理
        │   ├── useLabelResolver.ts      # 赛事名称解析
        │   └── useReadinessChecker.ts   # 材料就绪检查
        ├── components/         # 通用组件
        │   ├── AppLayout.tsx            # 全局布局
        │   ├── ProtectedRoute.tsx       # 路由守卫
        │   ├── CompetitionSelector.tsx  # 赛事选择器
        │   ├── JudgeStyleSelector.tsx   # 评委风格选择
        │   ├── VoiceSelector.tsx        # 音色选择
        │   ├── VoiceClonePanel.tsx      # 音色克隆面板
        │   ├── ModeSwitch.tsx           # 路演模式切换
        │   ├── RadarChart.tsx           # 雷达图（评审维度可视化）
        │   ├── TextReviewPanel.tsx      # 文本评审面板
        │   ├── ReviewSelectionDialog.tsx # 评审选项对话框
        │   ├── AIProcessingCard.tsx     # AI 处理中状态卡片
        │   ├── NetworkStatusBar.tsx     # 网络状态提示
        │   ├── OnboardingGuide.tsx      # 新手引导
        │   ├── ProjectTree.tsx          # 项目树
        │   └── BackButton.tsx           # 返回按钮
        └── pages/              # 页面
            ├── Login.tsx / Register.tsx
            ├── Home.tsx
            ├── ProjectList.tsx / ProjectCreate.tsx / ProjectDashboard.tsx
            ├── MaterialCenter.tsx
            ├── TextReview.tsx
            ├── OfflineReview.tsx
            ├── LivePresentation.tsx
            └── ReviewHistory.tsx / ReviewDetail.tsx
```

---

## 4. 数据库设计

基于 Supabase PostgreSQL，所有表启用 RLS 行级安全策略。

| 表名 | 用途 |
|------|------|
| `profiles` | 用户扩展信息（display_name） |
| `projects` | 参赛项目（赛事、赛道、组别、当前阶段） |
| `project_materials` | 项目材料（支持版本管理，is_latest 标记） |
| `reviews` | 评审记录（类型、风格、总分、状态） |
| `review_details` | 评审维度详情（维度得分 + 子项 + 建议） |
| `custom_voices` | 用户自定义音色 |
| `project_tags` | 自定义标签 |
| `project_tag_associations` | 标签-项目关联 |
| `project_profiles` | AI 提取的项目简介 |
| `stage_configs` | 比赛阶段日期配置 |

材料类型：`bp`、`text_ppt`、`presentation_ppt`、`presentation_video`、`presentation_audio`

---

## 5. 核心功能模块

### 5.1 认证系统
- Supabase Auth（邮箱 + 密码注册/登录）
- JWT token 存储于 localStorage，前端 Axios 拦截器自动附加

### 5.2 项目管理
- 创建项目时选择赛事 → 赛道 → 组别
- 项目仪表盘展示材料状态、评审历史
- 支持自定义标签分类
- 阶段日期配置

### 5.3 材料中心
- 支持上传 BP（PDF/DOCX）、文本 PPT、路演 PPT、路演视频/音频
- 文件大小限制：PPT 50MB，视频 500MB
- 材料版本管理（自动递增版本号，标记最新版）
- PPT 自动转图片存储（用于多模态 AI 分析）

### 5.4 文本评审
- AI 分析上传的文本材料（BP、PPT 等）
- 按评审规则维度打分，生成子项评价和改进建议
- 支持选择评委风格（严厉 / 温和 / 学术）
- 支持选择参与评审的材料类型

### 5.5 离线评审
- AI 观看路演视频 + 分析路演 PPT
- 三维评审：内容维度打分 + PPT 视觉评审 + 演讲者表现评价
- Deepgram STT 将音频转文字辅助分析

### 5.6 现场路演（Vision-Agents）
- 基于 Vision-Agents 框架创建 AI 评委 Agent
- Agent 通过 GetStream WebRTC 加入视频通话
- 使用 Qwen Realtime 进行实时多模态对话
- 两种模式：提问模式 / 建议模式（可实时切换）
- 支持分享链接邀请他人观看
- 支持自定义评委音色（预设 + 克隆）

### 5.7 评审历史与导出
- 查看所有历史评审记录
- 评审详情页展示雷达图 + 维度得分 + 建议
- 支持导出 PDF 评审报告

---

## 6. 比赛阶段与评审流程

```
校赛文本评审 → 校赛路演 → 省赛文本评审 → 省赛路演 → 国赛文本评审 → 国赛路演
(school_text)  (school_    (province_    (province_    (national_    (national_
                presentation) text)        presentation) text)        presentation)
```

每个阶段可进行对应类型的评审，评审规则按 `赛事/赛道/组别` 三级目录组织。

当前支持的赛事：**国创赛**（guochuangsai）
- 赛道：高教、产业、红旅、萌芽、职教
- 组别（以高教为例）：本科创业、本科创意、研究生创业、研究生创意

---

## 7. API 概览

| 前缀 | 模块 | 说明 |
|------|------|------|
| `/api/auth` | 认证 | 注册、登录、用户信息 |
| `/api/competitions` | 赛事配置 | 赛事/赛道/组别列表、评审规则、名称映射 |
| `/api/projects` | 项目管理 | CRUD、阶段日期配置 |
| `/api/projects/{id}/materials` | 材料管理 | 上传、列表、下载、状态查询 |
| `/api/projects/{id}/reviews` | 评审 | 文本评审、离线评审、历史、详情、PDF 导出 |
| `/api/projects/{id}/live` | 现场路演 | 创建/结束会话、模式切换、分享链接 |
| `/api/judge-styles` | 评委风格 | 风格列表 |
| `/api/voices` | 音色管理 | 预设音色、自定义音色 CRUD |
| `/api/tags` | 标签 | 自定义标签 CRUD |

---

## 8. 外部服务依赖

| 服务 | 用途 | 配置项 |
|------|------|--------|
| Supabase | 数据库 + 认证 + 文件存储 | `SUPABASE_URL`, `SUPABASE_KEY` |
| 通义千问 (DashScope) | 多模态 AI 评审 | `DASHSCOPE_API_KEY`, `DASHSCOPE_MODEL` |
| GetStream | WebRTC 音视频通话 | `GETSTREAM_API_KEY`, `GETSTREAM_API_SECRET` |
| Deepgram | 语音转文字 | `DEEPGRAM_API_KEY` |

---

## 9. 开发与部署

### 本地开发
```bash
# 一键启动（需要 uv + npm）
./start.sh dev

# 或分别启动：
# 后端
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000
# 前端
cd frontend && npm install && npm run dev
```

### Docker 部署
```bash
./start.sh docker
# 或
docker compose up --build
```

### 访问地址
- 前端：http://localhost:3000
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 10. Prompt 与知识体系

系统的 AI 评审质量依赖三层内容：

1. **评审规则**（`rules/`）— 各赛事/赛道/组别的官方评审标准和维度
2. **评委经验知识库**（`knowledge/`）— 按材料类型组织的评审经验和注意事项
3. **Prompt 模板**（`prompts/templates/`）— 各场景的 prompt 模板，动态注入规则、知识、材料内容
4. **评委风格**（`prompts/styles/`）— strict / gentle / academic 三种人格化风格描述

---

## 11. 已知约束与待改进

- 后端测试目录尚未建立（`backend/tests/` 不存在）
- 当前仅支持国创赛一个赛事的规则
- 现场路演的 AI 评委依赖 Vision-Agents + Qwen Realtime 的稳定性
- 文件上传大小限制硬编码在配置中

---

## 12. 变更日志

| 日期 | 变更内容 |
|------|----------|
| 2026-03-26 | 初始文档创建，记录项目全景 |
