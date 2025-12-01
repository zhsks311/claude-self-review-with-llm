"""Build static site from markdown files."""

import os
import re
from pathlib import Path
from typing import Optional

import mistune

from .template import render_template


def extract_title(markdown_content: str, filename: str) -> str:
    """Extract title from markdown content.

    Looks for first h1 heading (# Title). Falls back to filename if not found.

    Args:
        markdown_content: Raw markdown string.
        filename: Filename to use as fallback.

    Returns:
        Extracted title string.
    """
    # Look for first # heading
    match = re.search(r"^#\s+(.+)$", markdown_content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # Fallback to filename without extension
    return Path(filename).stem.replace("-", " ").replace("_", " ").title()


def convert_markdown_to_html(markdown_content: str) -> str:
    """Convert markdown to HTML using mistune.

    Args:
        markdown_content: Raw markdown string.

    Returns:
        HTML string.
    """
    md = mistune.create_markdown()
    return md(markdown_content)


def build_file(
    source_path: Path,
    output_path: Path,
    template_path: Optional[Path] = None
) -> None:
    """Build single markdown file to HTML.

    Args:
        source_path: Path to source .md file.
        output_path: Path to output .html file.
        template_path: Optional custom template path.
    """
    # Read markdown
    markdown_content = source_path.read_text(encoding="utf-8")

    # Extract title and convert to HTML
    title = extract_title(markdown_content, source_path.name)
    html_content = convert_markdown_to_html(markdown_content)

    # Render with template
    full_html = render_template(
        content=html_content,
        title=title,
        template_path=template_path
    )

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    output_path.write_text(full_html, encoding="utf-8")


def build_site(
    content_dir: Path,
    output_dir: Path,
    template_path: Optional[Path] = None
) -> int:
    """Build entire site from content directory.

    Args:
        content_dir: Directory containing .md files.
        output_dir: Directory to output .html files.
        template_path: Optional custom template path.

    Returns:
        Number of files processed.
    """
    count = 0

    for root, dirs, files in os.walk(content_dir):
        for filename in files:
            if not filename.endswith(".md"):
                continue

            # Calculate paths
            source_path = Path(root) / filename
            relative_path = source_path.relative_to(content_dir)
            output_path = output_dir / relative_path.with_suffix(".html")

            # Build file
            build_file(source_path, output_path, template_path)
            print(f"  {relative_path} -> {output_path.relative_to(output_dir)}")
            count += 1

    return count
