"""Local development server using Flask."""

from pathlib import Path

from flask import Flask, send_from_directory, abort


def create_app(static_dir: Path) -> Flask:
    """Create Flask app for serving static files.

    Args:
        static_dir: Directory containing static files to serve.

    Returns:
        Configured Flask application.
    """
    app = Flask(__name__)
    static_dir = static_dir.resolve()

    @app.route("/")
    def index():
        """Serve index.html from root."""
        index_path = static_dir / "index.html"
        if index_path.exists():
            return send_from_directory(static_dir, "index.html")
        else:
            # List available files
            files = list(static_dir.glob("*.html"))
            if files:
                links = "".join(
                    f'<li><a href="/{f.name}">{f.name}</a></li>'
                    for f in files
                )
                return f"<h1>Available Pages</h1><ul>{links}</ul>"
            return "<h1>No HTML files found</h1>", 404

    @app.route("/<path:filename>")
    def serve_file(filename):
        """Serve static files from the directory."""
        file_path = static_dir / filename

        # Security check: prevent path traversal
        try:
            file_path.resolve().relative_to(static_dir)
        except ValueError:
            abort(403)

        if file_path.exists() and file_path.is_file():
            return send_from_directory(static_dir, filename)

        # Try adding .html extension
        html_path = static_dir / f"{filename}.html"
        if html_path.exists():
            return send_from_directory(static_dir, f"{filename}.html")

        abort(404)

    return app


def serve_site(directory: Path, port: int = 8000) -> None:
    """Start development server.

    Args:
        directory: Directory to serve.
        port: Port number to listen on.
    """
    app = create_app(directory)
    print(f"Serving {directory} at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    app.run(host="0.0.0.0", port=port, debug=True)
