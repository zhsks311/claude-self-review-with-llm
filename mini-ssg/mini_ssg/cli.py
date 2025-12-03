#!/usr/bin/env python3
"""CLI entry point for mini-ssg."""

import argparse
import sys
from pathlib import Path

from .builder import build_site
from .server import serve_site


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mini-ssg",
        description="A minimal static site generator"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # build command
    build_parser = subparsers.add_parser("build", help="Build static site from markdown")
    build_parser.add_argument("content", type=str, help="Content directory with .md files")
    build_parser.add_argument("output", type=str, help="Output directory for HTML files")
    build_parser.add_argument(
        "-t", "--template",
        type=str,
        default=None,
        help="Custom template file (default: built-in template)"
    )

    # serve command
    serve_parser = subparsers.add_parser("serve", help="Serve the built site locally")
    serve_parser.add_argument(
        "directory",
        type=str,
        nargs="?",
        default="./output",
        help="Directory to serve (default: ./output)"
    )
    serve_parser.add_argument(
        "-p", "--port",
        type=int,
        default=8000,
        help="Port to serve on (default: 8000)"
    )

    args = parser.parse_args()

    if args.command == "build":
        content_path = Path(args.content)
        output_path = Path(args.output)
        template_path = Path(args.template) if args.template else None

        if not content_path.exists():
            print(f"Error: Content directory '{content_path}' does not exist")
            sys.exit(1)

        build_site(content_path, output_path, template_path)
        print(f"Site built successfully: {output_path}")

    elif args.command == "serve":
        directory = Path(args.directory)
        if not directory.exists():
            print(f"Error: Directory '{directory}' does not exist")
            sys.exit(1)

        serve_site(directory, args.port)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
