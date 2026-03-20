# Requirements Document

## Introduction

本需求文档描述了创赛评审系统（web_ui_agent）的第二轮系统优化功能。涵盖七个核心改进方向：PDF导出中文标签修复、文本评审功能增强（含PPT视觉评审）、离线评审功能增强（含音频STT支持）、现场路演prompt材料注入优化、API调用耗时监控与性能分析、前端用户引导与自动触发流程优化、以及前端并发操作状态管理修复。

## Glossary

- **Export_Service**: 项目评审报告PDF导出服务，负责生成包含项目信息、材料状态、评审结果的PDF报告
- **Text_Review_Service**: 文本评审服务，基于文本PPT和BP等材料调用AI进行多维度评分
- **Offline_Review_Service**: 离线路演评审服务，基于路演视频和PPT调用AI进行综合评审
- **Live_Presentation_Service**: 现场路演服务，管理实时音视频路演会话和AI评委交互
- **Label_Resolver**: 前端标签解析模块，负责将英文ID（如guochuangsai）映射为中文标签
- **Name_Mappings**: 后端名称映射字典，包含COMPETITION_NAMES、TRACK_NAMES、GROUP_NAMES三组英文ID到中文名称的映射
- **STT_Service**: 语音转文字服务，将音频或视频中的语音内容转录为文本
- **Qwen_Long**: 通义千问长文本模型，用于基于规则和材料内容进行文本评审打分
- **Qwen_VL_Max**: 通义千问视觉语言模型，用于对PPT进行视觉层面的评审
- **PPT_Visual_Review**: PPT视觉评审功能，使用Qwen_VL_Max对PPT的视觉设计进行独立评价
- **Review_Record**: 评审记录，存储在reviews表中的一条评审结果数据
- **Review_History_Table**: 评审历史表格，前端展示所有评审记录的列表页面
- **Project_Profile**: 项目简介，从BP和文本PPT中提取的结构化项目信息
- **Prompt_Service**: Prompt模板管理服务，负责组装评委风格、评审规则、知识库和材料内容为最终prompt
- **TextReviewPanel**: 前端评审结果展示组件，用于渲染评分表格、维度详情和建议
- **API_Timing_Logger**: API调用耗时日志模块，负责记录每个服务API调用各阶段的耗时信息
- **Onboarding_Guide**: 前端用户引导模块，在关键操作节点向用户提示下一步可用功能
- **Auto_Trigger_Service**: 自动触发服务，在特定材料上传完成后自动调用关联的AI处理流程
- **Concurrent_State_Manager**: 前端并发状态管理器，负责独立维护多个异步操作的加载状态，确保各操作互不干扰

## Requirements

### Requirement 1: PDF导出中文标签

**User Story:** 作为用户，我希望导出的项目评审报告PDF中赛事、赛道、组别等字段显示中文名称，以便报告内容清晰可读。

#### Acceptance Criteria

1. WHEN Export_Service 生成PDF报告时，THE Export_Service SHALL 将项目的competition字段值通过Name_Mappings转换为对应的中文名称后写入PDF
2. WHEN Export_Service 生成PDF报告时，THE Export_Service SHALL 将项目的track字段值通过Name_Mappings转换为对应的中文名称后写入PDF
3. WHEN Export_Service 生成PDF报告时，THE Export_Service SHALL 将项目的group字段值通过Name_Mappings转换为对应的中文名称后写入PDF
4. WHEN Export_Service 生成PDF报告中的评审结果表格时，THE Export_Service SHALL 将review_type字段值转换为中文标签（text_review显示为"文本评审"，offline_presentation显示为"离线路演"，live_presentation显示为"现场路演"）
5. IF Name_Mappings中不存在某个英文ID的映射，THEN THE Export_Service SHALL 回退显示原始英文ID值

### Requirement 2: 文本评审材料选择简化

**User Story:** 作为用户，我希望文本评审只需要文本PPT和文本BP即可进行，以便简化评审流程。

#### Acceptance Criteria

1. THE Text_Review_Service SHALL 仅支持text_ppt和bp两种材料类型作为文本评审的有效输入
2. WHEN 用户发起文本评审时，THE 前端文本评审页面 SHALL 仅展示文本PPT和文本BP两种材料的选择项
3. WHEN 用户未上传文本PPT且未上传BP时，THE Text_Review_Service SHALL 返回400错误并提示"请先上传文本PPT或BP材料"

### Requirement 3: 文本评审记录中体现所选材料

**User Story:** 作为用户，我希望在评审历史表格中看到每次文本评审时选择了哪些材料，以便追溯评审依据。

#### Acceptance Criteria

1. WHEN Text_Review_Service 存储评审记录时，THE Text_Review_Service SHALL 将用户选择的材料类型列表保存到reviews表的selected_materials字段中
2. WHEN Review_History_Table 展示文本评审记录时，THE Review_History_Table SHALL 在表格中增加一列显示该次评审所选的材料类型（以中文标签形式呈现，如"文本PPT、BP"）
3. WHEN 查看历史评审记录详情时，THE 评审详情页面 SHALL 展示该次评审所使用的材料类型列表

### Requirement 4: 文本PPT视觉评审

**User Story:** 作为用户，我希望在文本评审中勾选了文本PPT时，系统能额外使用视觉模型对PPT进行独立的视觉评审，以便获得PPT设计层面的专业反馈。

#### Acceptance Criteria

1. WHEN 用户在文本评审中勾选了text_ppt材料时，THE Text_Review_Service SHALL 在Qwen_Long完成文本评审后，额外调用Qwen_VL_Max对文本PPT进行一轮独立的视觉评审
2. THE PPT_Visual_Review SHALL 从信息结构、信息密度、视觉设计、图示表达、说服力、完整性六个维度对PPT进行评价
3. WHEN PPT视觉评审完成时，THE Text_Review_Service SHALL 将视觉评审结果与文本评审结果合并返回给前端
4. WHEN PPT被视觉评审判定为优秀时，THE PPT_Visual_Review SHALL 直接给出"PPT整体表现优秀"的正面评价，而非强行提出修改建议
5. THE PPT_Visual_Review SHALL 使用独立管理的prompt模板文件（prompts/templates/ppt_visual_review.md），该prompt基于原文本PPT视觉.md的评审维度设计
6. WHEN PPT视觉评审prompt模板创建完成后，THE 系统 SHALL 删除backend/文本PPT视觉.md原始参考文件
7. WHEN 前端展示评审结果时，THE TextReviewPanel SHALL 将PPT视觉评审结果作为独立区块展示，与文本评审打分表格区分开

### Requirement 5: 离线评审支持音频文件上传

**User Story:** 作为用户，我希望在离线评审中能上传音频文件（除视频外），以便仅有音频录制的路演也能进行评审。

#### Acceptance Criteria

1. THE Offline_Review_Service SHALL 支持用户上传音频文件（mp3、wav、m4a、aac格式）作为路演材料
2. WHEN 用户上传音频文件时，THE 材料管理服务 SHALL 将音频文件存储为presentation_audio类型
3. WHEN 用户已上传路演视频或路演音频中的至少一种时，THE Offline_Review_Service SHALL 允许发起离线评审
4. WHEN 前端离线评审页面加载时，THE 前端 SHALL 展示路演视频和路演音频两种媒体材料的上传状态

### Requirement 6: 离线评审STT转文字

**User Story:** 作为用户，我希望系统能将路演视频或音频中的语音自动转为文字，以便AI能基于文字内容进行深度评审。

#### Acceptance Criteria

1. WHEN 用户发起离线评审时，THE Offline_Review_Service SHALL 调用STT_Service将视频或音频中的语音内容转录为文本
2. THE STT_Service SHALL 使用.env中配置的DEEPGRAM_API_KEY调用Deepgram API进行语音转文字
3. WHEN STT转录完成后，THE Offline_Review_Service SHALL 将转录文本与路演PPT（PDF）一起传给Qwen_Long进行文本层面的评审和打分
4. IF STT转录失败，THEN THE Offline_Review_Service SHALL 返回错误信息并提示用户"语音转文字失败，请检查音频质量或稍后重试"

### Requirement 7: 离线评审PPT视觉评审

**User Story:** 作为用户，我希望离线评审也能对路演PPT进行视觉层面的独立评审，以便获得与文本评审一致的PPT设计反馈。

#### Acceptance Criteria

1. WHEN 离线评审流程中存在路演PPT时，THE Offline_Review_Service SHALL 在Qwen_Long完成文本评审后，额外调用Qwen_VL_Max对路演PPT进行一轮独立的视觉评审
2. THE Offline_Review_Service SHALL 复用PPT_Visual_Review的prompt模板和评审维度
3. WHEN 前端展示离线评审结果时，THE 前端 SHALL 将PPT视觉评审结果作为独立区块展示

### Requirement 8: 离线评审路演者评价

**User Story:** 作为用户，我希望离线评审能针对路演者的路演表现给出专门的评价和建议，以便路演者改进演讲技巧。

#### Acceptance Criteria

1. THE Offline_Review_Service SHALL 在评审结果中增加"路演表现评价"模块，针对路演者的语言表达、节奏控制、逻辑清晰度、互动感等方面给出评价
2. THE Offline_Review_Service SHALL 基于STT转录文本分析路演者的表达特点，给出具体的改进建议
3. WHEN 前端展示离线评审结果时，THE 前端 SHALL 将路演表现评价作为独立区块展示在评审结果末尾

### Requirement 9: 现场路演prompt注入项目简介

**User Story:** 作为用户，我希望现场路演的AI评委在初始化时能获取项目简介信息，以便AI评委对项目有更全面的了解。

#### Acceptance Criteria

1. WHEN Live_Presentation_Service 初始化路演会话时，THE Live_Presentation_Service SHALL 查询该项目的Project_Profile数据
2. WHEN Project_Profile存在时，THE Live_Presentation_Service SHALL 将项目简介的结构化字段（团队介绍、所属领域、创业状态、已有成果、产品链接、下一步目标）拼接到prompt的材料描述部分
3. IF Project_Profile不存在，THEN THE Live_Presentation_Service SHALL 仅使用路演PPT文件信息作为材料描述（保持当前行为不变）

### Requirement 10: 评审结果界面美化

**User Story:** 作为用户，我希望评审结果界面的表格信息呈现更加整齐美观，以便更清晰地阅读评审报告。

#### Acceptance Criteria

1. THE TextReviewPanel SHALL 对评分维度表格使用统一的列宽、对齐方式和间距，确保各维度评分数据对齐展示
2. THE TextReviewPanel SHALL 对子项评价列表使用一致的缩进和分隔样式
3. THE TextReviewPanel SHALL 对改进建议文本使用合理的段落间距和列表样式
4. THE TextReviewPanel SHALL 确保在不同屏幕宽度下表格内容不出现错位或溢出

### Requirement 11: API调用耗时监控

**User Story:** 作为开发者，我希望能够查看每个服务API调用各阶段的耗时信息，以便定位性能瓶颈并进行针对性优化。

#### Acceptance Criteria

1. WHEN 后端接收到API请求时，THE API_Timing_Logger SHALL 记录请求开始时间戳
2. WHEN 后端API处理过程中调用外部服务（如Qwen_Long、Qwen_VL_Max、STT_Service、Deepgram API）时，THE API_Timing_Logger SHALL 分别记录每次外部服务调用的开始时间和结束时间
3. WHEN 后端API请求处理完成时，THE API_Timing_Logger SHALL 在服务端日志中输出完整的耗时分解信息，包含总耗时、各外部服务调用耗时、以及业务逻辑处理耗时
4. WHEN 前端发起API请求时，THE 前端 SHALL 在浏览器控制台中记录请求发起时间和响应接收时间，并输出该请求的前端侧总耗时
5. THE API_Timing_Logger SHALL 对Text_Review_Service、Offline_Review_Service、Live_Presentation_Service、Export_Service四个核心服务的所有API端点启用耗时监控
6. THE API_Timing_Logger SHALL 以结构化格式（包含api_path、total_ms、stages数组）输出日志，便于后续分析和聚合

### Requirement 12: 前端用户引导与自动触发

**User Story:** 作为用户，我希望在完成关键操作后系统能引导我进行下一步操作，并在条件满足时自动触发AI处理流程，以便减少手动操作步骤、提升使用效率。

#### Acceptance Criteria

1. WHEN 用户创建项目成功后，THE Onboarding_Guide SHALL 弹出引导提示，告知用户可以上传文本PPT、BP等材料文件
2. WHEN 用户关闭引导提示后，THE Onboarding_Guide SHALL 记录该提示已展示状态，同一项目内不再重复弹出相同引导
3. WHEN 用户完成文本BP或文本PPT的上传后，THE Auto_Trigger_Service SHALL 自动调用AI项目简历总结功能生成Project_Profile
4. WHEN Auto_Trigger_Service 自动触发AI项目简历总结时，THE 前端 SHALL 在对应的Project_Profile区域展示"正在生成项目简介..."的处理中状态标记
5. WHEN AI项目简历总结处理完成后，THE 前端 SHALL 将处理中状态标记替换为生成的Project_Profile内容
6. IF Auto_Trigger_Service 自动触发的AI项目简历总结失败，THEN THE 前端 SHALL 展示错误提示并提供"重试"按钮

### Requirement 13: 前端并发操作状态管理修复

**User Story:** 作为用户，我希望在同时进行多个异步操作（如同时上传多个文件、同时触发多个AI处理）时，每个操作的加载状态能独立维护，以便准确了解每个操作的实际进度。

#### Acceptance Criteria

1. THE Concurrent_State_Manager SHALL 为每个异步操作分配独立的状态标识，确保多个操作的加载状态互不覆盖
2. WHEN 用户在上传商业计划书的过程中发起文本PPT上传时，THE Concurrent_State_Manager SHALL 同时维护两个独立的上传进度状态，商业计划书的上传加载状态不受文本PPT上传的影响
3. WHEN 用户在生成简历的过程中切换到其他页面再切换回来时，THE Concurrent_State_Manager SHALL 恢复并展示该操作的当前实际状态（处理中、已完成或已失败）
4. WHEN 用户在某个AI处理进行中时发起另一个API调用，THE Concurrent_State_Manager SHALL 保持原有AI处理的加载状态不变，同时展示新API调用的加载状态
5. THE Concurrent_State_Manager SHALL 对以下操作类型实施独立状态管理：文件上传（按材料类型区分）、AI简历生成、文本评审、离线评审、PDF导出
6. WHEN 某个异步操作完成或失败时，THE Concurrent_State_Manager SHALL 仅更新该操作对应的状态标识，其他进行中的操作状态保持不变
