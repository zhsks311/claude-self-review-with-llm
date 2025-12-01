"""Simple template engine with {{variable}} substitution."""

import re
from pathlib import Path
from typing import Dict, Optional


DEFAULT_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{title}}</title>
    <style>
        body {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
        }
        pre {
            background: #f4f4f4;
            padding: 10px;
            overflow-x: auto;
        }
        code {
            background: #f4f4f4;
            padding: 2px 5px;
        }
    </style>
</head>
<body>
    <article>
        {{content}}
    </article>
</body>
</html>
"""


class TemplateEngine:
    """Simple template engine that replaces {{variable}} patterns."""

    def __init__(self, template_path: Optional[Path] = None):
        """Initialize template engine.

        Args:
            template_path: Path to custom template file. Uses default if None.
        """
        if template_path and template_path.exists():
            self.template = template_path.read_text(encoding="utf-8")
        else:
            self.template = DEFAULT_TEMPLATE

    def render(self, variables: Dict[str, str]) -> str:
        """Render template with given variables.

        Args:
            variables: Dict mapping variable names to values.

        Returns:
            Rendered HTML string.
        """
        result = self.template

        # Find all {{variable}} patterns
        pattern = r"\{\{(\w+)\}\}"

        def replace_var(match):
            var_name = match.group(1)
            return variables.get(var_name, match.group(0))

        result = re.sub(pattern, replace_var, result)

        return result


def render_template(
    content: str,
    title: str,
    template_path: Optional[Path] = None,
    **extra_vars
) -> str:
    """Convenience function to render content with template.

    Args:
        content: HTML content to insert.
        title: Page title.
        template_path: Optional custom template path.
        **extra_vars: Additional template variables.

    Returns:
        Rendered HTML string.
    """
    engine = TemplateEngine(template_path)
    variables = {
        "content": content,
        "title": title,
        **extra_vars
    }
    return engine.render(variables)
