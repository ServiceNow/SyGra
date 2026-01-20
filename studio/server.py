"""
SyGra Workflow UI Server.

Launches the FastAPI backend with static file serving for the UI.
"""

import os
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from studio.api import create_app


def create_server(
    tasks_dir: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    cors_origins: Optional[list] = None,
    use_svelte_ui: Optional[bool] = None,
) -> FastAPI:
    """
    Create the combined API and UI server.

    Args:
        tasks_dir: Directory containing SyGra task workflows.
        host: Host to bind to.
        port: Port to listen on.
        cors_origins: List of allowed CORS origins.
        use_svelte_ui: Use the new Svelte-based UI (requires npm build).

    Returns:
        Configured FastAPI application.
    """
    # Read from environment if not explicitly set
    if tasks_dir is None:
        tasks_dir = os.environ.get("SYGRA_TASKS_DIR")
    if use_svelte_ui is None:
        use_svelte_ui = os.environ.get("SYGRA_USE_SVELTE_UI", "0") == "1"

    # Create the API app
    app = create_app(tasks_dir=tasks_dir, cors_origins=cors_origins)

    # Determine which UI to serve
    base_dir = Path(__file__).parent
    svelte_build_dir = base_dir / "frontend" / "build"
    legacy_ui_dir = base_dir / "ui"

    # Check for Svelte build or use legacy
    use_svelte = use_svelte_ui and svelte_build_dir.exists() and (svelte_build_dir / "index.html").exists()

    if use_svelte:
        ui_dir = svelte_build_dir
    else:
        ui_dir = legacy_ui_dir
        if use_svelte_ui:
            print("⚠️  UI not built. Run 'npm run build' in frontend/. Falling back to legacy UI.")
        print("📦 Running SyGra Studio with legacy UI")

    # Serve the UI
    @app.get("/")
    async def serve_ui():
        """Serve the main UI page."""
        return FileResponse(ui_dir / "index.html")

    # For Svelte SPA, serve index.html for all non-API routes
    if use_svelte:
        @app.get("/{path:path}")
        async def serve_spa(path: str):
            """Serve SPA for client-side routing."""
            if path.startswith("api/"):
                return None  # Let API routes handle these
            file_path = ui_dir / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(ui_dir / "index.html")

        # Mount static assets
        app.mount("/_app", StaticFiles(directory=str(ui_dir / "_app")), name="svelte_app")
    else:
        # Mount static files for legacy UI
        if (ui_dir / "static").exists():
            app.mount("/static", StaticFiles(directory=str(ui_dir / "static")), name="static")

    return app


def run_server(
    tasks_dir: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
    use_svelte_ui: bool = False,
):
    """
    Run the SyGra Workflow UI server.

    Args:
        tasks_dir: Directory containing SyGra task workflows.
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.
        log_level: Logging level.
        use_svelte_ui: Use the new Svelte-based UI (requires npm build).
    """
    # Build dynamic banner
    server_url = f"http://{host}:{port}"
    tasks_display = tasks_dir or 'default'

    # ASCII art title
    title_lines = [
        "      ____         ____                 ",
        "     / ___| _   _ / ___|_ __ __ _       ",
        "     \\___ \\| | | | |  _| '__/ _` |      ",
        "      ___) | |_| | |_| | | | (_| |      ",
        "     |____/ \\__, |\\____|_|  \\__,_|      ",
        "            |___/                       ",
        "                                          ",
        "            ✦  S T U D I O  ✦           ",
    ]

    info_lines = [
        f"Server:  {server_url}",
        f"Tasks:   {tasks_display}",
        "",
        "Press Ctrl+C to stop",
    ]

    # Calculate box width based on content
    all_content = title_lines + info_lines
    content_width = max(len(line) for line in all_content)
    box_width = max(54, content_width + 6)  # minimum 54 for the ASCII art

    def center_line(text, width):
        """Center text within given width."""
        padding = width - len(text)
        left_pad = padding // 2
        right_pad = padding - left_pad
        return " " * left_pad + text + " " * right_pad

    def left_line(text, width):
        """Left-align text with padding."""
        padding = width - len(text)
        return "  " + text + " " * (padding - 2)

    # Print banner
    print()
    print(f"╔{'═' * box_width}╗")
    print(f"║{' ' * box_width}║")

    # Title (centered)
    for line in title_lines:
        print(f"║{center_line(line, box_width)}║")

    # Horizontal rule
    print(f"╠{'─' * box_width}╣")
    print(f"║{' ' * box_width}║")

    # Info (left-aligned)
    for line in info_lines:
        padded = left_line(line, box_width)
        print(f"║{padded}║")

    print(f"║{' ' * box_width}║")
    print(f"╚{'═' * box_width}╝")
    print()

    # Set environment variables
    if tasks_dir:
        os.environ["SYGRA_TASKS_DIR"] = tasks_dir
    os.environ["SYGRA_USE_SVELTE_UI"] = "1" if use_svelte_ui else "0"

    # Filter known third-party deprecation warnings (uvicorn's websockets usage)
    # This is a known issue: https://github.com/encode/uvicorn/issues/2344
    import warnings
    warnings.filterwarnings("ignore", message="websockets.legacy", category=DeprecationWarning)
    warnings.filterwarnings("ignore", message="websockets.server.WebSocketServerProtocol", category=DeprecationWarning)

    uvicorn.run(
        "studio.server:create_server",
        factory=True,
        host=host,
        port=port,
        reload=reload,
        log_level=log_level,
    )


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="SyGra Workflow Visualizer - View and run SyGra workflows in a web UI"
    )

    parser.add_argument(
        "--tasks-dir", "-t",
        type=str,
        default=None,
        help="Directory containing SyGra task workflows"
    )

    parser.add_argument(
        "--host", "-H",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8000,
        help="Port to listen on (default: 8000)"
    )

    parser.add_argument(
        "--reload", "-r",
        action="store_true",
        help="Enable auto-reload for development"
    )

    parser.add_argument(
        "--log-level", "-l",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)"
    )

    parser.add_argument(
        "--svelte", "-s",
        action="store_true",
        help="Use the new Svelte-based UI (requires 'npm run build' in frontend/)"
    )

    args = parser.parse_args()

    run_server(
        tasks_dir=args.tasks_dir,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        use_svelte_ui=args.svelte,
    )


if __name__ == "__main__":
    main()
