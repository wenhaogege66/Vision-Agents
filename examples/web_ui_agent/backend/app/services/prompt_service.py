"""Prompt模板管理服务：管理评委风格和功能模板，组装最终prompt。

从 prompts/styles/ 目录读取评委风格角色描述文件，
从 prompts/templates/ 目录读取功能模板文件，
按照固定顺序拼接最终prompt。
"""

import logging
from pathlib import Path

from app.models.schemas import JudgeStyleInfo

logger = logging.getLogger(__name__)

# Prompt文件根目录（相对于 backend/）
_PROMPTS_BASE = Path(__file__).resolve().parent.parent.parent / "prompts"

# 输出格式分隔标记
_OUTPUT_FORMAT_MARKER = "<!-- OUTPUT_FORMAT -->"

# 交互模式指令
_INTERACTION_MODE_INSTRUCTIONS: dict[str, str] = {
    "question": (
        "\n\n## 交互模式：提问模式\n\n"
        "当前处于提问模式。请针对路演内容中的薄弱环节提出尖锐、有深度的问题，"
        "帮助选手发现项目中的逻辑漏洞、数据缺陷和商业风险。"
        "每次只提一个问题，等待选手回答后再继续追问。\n"
    ),
    "suggestion": (
        "\n\n## 交互模式：建议模式\n\n"
        "当前处于建议模式。请对路演内容给出建设性的改进建议，"
        "按重要程度排序，先说最关键的改进点。"
        "建议应具体、可操作，帮助选手提升项目质量和路演表现。\n"
    ),
}


def _parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """解析Markdown文件的YAML front-matter。

    Args:
        content: 完整的Markdown文件内容

    Returns:
        (metadata_dict, body_content) 元组
    """
    metadata: dict[str, str] = {}
    body = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            # parts[0] is empty (before first ---), parts[1] is YAML, parts[2] is body
            yaml_text = parts[1].strip()
            body = parts[2].strip()

            for line in yaml_text.splitlines():
                line = line.strip()
                if ":" in line:
                    key, _, value = line.partition(":")
                    metadata[key.strip()] = value.strip()

    return metadata, body


class PromptService:
    """Prompt模板管理服务。

    管理评委风格角色描述和功能模板，
    按固定顺序组装最终prompt。
    """

    def __init__(self, prompts_base: Path | None = None):
        """初始化Prompt服务。

        Args:
            prompts_base: Prompt文件根目录，默认为 backend/prompts/
        """
        self._prompts_base = prompts_base or _PROMPTS_BASE

    @property
    def prompts_base(self) -> Path:
        """Prompt文件根目录"""
        return self._prompts_base

    @property
    def _styles_dir(self) -> Path:
        return self._prompts_base / "styles"

    @property
    def _templates_dir(self) -> Path:
        return self._prompts_base / "templates"

    def list_styles(self) -> list[JudgeStyleInfo]:
        """列出所有可用评委风格。

        扫描 prompts/styles/ 目录下的 .md 文件，
        从 YAML front-matter 中提取名称和描述。

        Returns:
            评委风格信息列表
        """
        styles_dir = self._styles_dir
        if not styles_dir.is_dir():
            logger.info("评委风格目录不存在: %s", styles_dir)
            return []

        styles: list[JudgeStyleInfo] = []
        for f in sorted(styles_dir.iterdir()):
            if not f.is_file() or f.suffix.lower() != ".md":
                continue

            content = f.read_text(encoding="utf-8")
            metadata, _ = _parse_front_matter(content)

            style_id = f.stem
            name = metadata.get("name", style_id)
            description = metadata.get("description", "")

            styles.append(
                JudgeStyleInfo(id=style_id, name=name, description=description)
            )

        return styles

    def load_style(self, style_id: str) -> str:
        """加载指定评委风格的角色描述内容。

        Args:
            style_id: 风格标识（如 strict, gentle, academic）

        Returns:
            角色描述Markdown内容（不含front-matter）

        Raises:
            FileNotFoundError: 风格文件不存在
        """
        style_path = self._styles_dir / f"{style_id}.md"
        if not style_path.is_file():
            raise FileNotFoundError(f"评委风格文件不存在: {style_id}")

        content = style_path.read_text(encoding="utf-8")
        _, body = _parse_front_matter(content)
        return body

    def load_template(self, template_name: str) -> str:
        """加载指定功能的prompt模板。

        Args:
            template_name: 模板名称（text_review / live_presentation / offline_review）

        Returns:
            模板Markdown内容

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        template_path = self._templates_dir / f"{template_name}.md"
        if not template_path.is_file():
            raise FileNotFoundError(f"Prompt模板文件不存在: {template_name}")

        return template_path.read_text(encoding="utf-8")

    def assemble_prompt(
        self,
        template_name: str,
        style_id: str,
        rules_content: str,
        knowledge_content: str,
        material_content: str,
        interaction_mode: str | None = None,
    ) -> str:
        """组装最终prompt。

        按以下顺序拼接：
        1. 角色描述（含风格）
        2. 评审规则
        3. 知识库内容
        4. 材料内容
        5. [现场路演] 交互模式指令
        6. 输出格式要求（从模板中提取）

        Args:
            template_name: 模板名称
            style_id: 评委风格标识
            rules_content: 评审规则文本
            knowledge_content: 知识库内容
            material_content: 材料内容描述
            interaction_mode: 交互模式（question/suggestion），仅现场路演使用

        Returns:
            组装后的完整prompt文本

        Raises:
            FileNotFoundError: 风格或模板文件不存在
        """
        # 1. 加载角色描述
        style_content = self.load_style(style_id)

        # 2. 加载模板并提取输出格式部分
        template_content = self.load_template(template_name)
        output_format = self._extract_output_format(template_content)

        # 3. 按顺序拼接
        parts: list[str] = []

        # 角色描述（含风格）
        parts.append(style_content)

        # 评审规则
        if rules_content.strip():
            parts.append(f"\n\n## 评审规则\n\n{rules_content}")

        # 知识库内容
        if knowledge_content.strip():
            parts.append(f"\n\n## 知识库参考\n\n{knowledge_content}")

        # 材料内容
        if material_content.strip():
            parts.append(f"\n\n## 评审材料\n\n{material_content}")

        # 交互模式指令（仅现场路演）
        if interaction_mode and interaction_mode in _INTERACTION_MODE_INSTRUCTIONS:
            parts.append(_INTERACTION_MODE_INSTRUCTIONS[interaction_mode])

        # 输出格式要求
        if output_format.strip():
            parts.append(f"\n\n{output_format}")

        return "".join(parts)

    def _extract_output_format(self, template_content: str) -> str:
        """从模板内容中提取输出格式部分。

        以 OUTPUT_FORMAT_MARKER 为分隔，取其后的内容作为输出格式。

        Args:
            template_content: 完整模板内容

        Returns:
            输出格式部分文本，若无标记则返回空字符串
        """
        if _OUTPUT_FORMAT_MARKER in template_content:
            _, _, output_section = template_content.partition(_OUTPUT_FORMAT_MARKER)
            return output_section.strip()
        return ""


# 模块级单例
prompt_service = PromptService()
