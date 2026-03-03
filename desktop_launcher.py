"""
JARVIS-OS Native Desktop Launcher
Launches the OS as a fullscreen native desktop window using pywebview.
This is what makes it feel like a real operating system, not a browser tab.
"""

import sys
import threading
import time
import logging
from pathlib import Path

logger = logging.getLogger("jarvis.launcher")

ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

# Load .env before anything else
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT_DIR / ".env", override=False)
except ImportError:
    pass


def start_server():
    """Start the FastAPI backend server in a background thread."""
    import uvicorn
    from config import load_config
    config = load_config()

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=config["server"]["port"],
        log_level="warning",
    )


def wait_for_server(port, timeout=30):
    """Wait until the server is ready."""
    import socket
    start = time.time()
    while time.time() - start < timeout:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            s.connect(("127.0.0.1", port))
            s.close()
            return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False


def launch_native_window():
    """Launch a native fullscreen window with the JARVIS-OS dashboard."""
    try:
        import webview

        from config import load_config
        config = load_config()
        port = config["server"]["port"]

        # Start server in background
        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()

        print("Starting JARVIS-OS server...")
        if not wait_for_server(port):
            print("ERROR: Server failed to start")
            sys.exit(1)

        print("Launching JARVIS-OS Desktop...")

        # Create native window
        window = webview.create_window(
            title="JARVIS-OS",
            url=f"http://127.0.0.1:{port}",
            width=1920,
            height=1080,
            fullscreen=True,
            frameless=True,
            easy_drag=False,
            background_color="#020810",
            text_select=True,
        )

        # Start the GUI event loop (auto-selects best backend per OS)
        gui_backend = None
        if sys.platform == "linux":
            gui_backend = "gtk"
        # Windows and macOS use default backends automatically

        webview.start(
            gui=gui_backend,
            debug=False,
        )

    except ImportError:
        print("=" * 60)
        print("  pywebview not installed. Falling back to browser mode.")
        print("  To get native desktop mode, install:")
        print("    pip install pywebview")
        print("=" * 60)
        launch_browser_mode()


def launch_browser_mode():
    """Fallback: launch in the system browser."""
    import webbrowser
    from config import load_config
    config = load_config()
    port = config["server"]["port"]

    # Start server in background
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    print("Starting JARVIS-OS server...")
    if not wait_for_server(port):
        print("ERROR: Server failed to start")
        sys.exit(1)

    url = f"http://127.0.0.1:{port}"
    print(f"Opening JARVIS-OS at {url}")
    webbrowser.open(url)

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nJARVIS-OS shutting down...")


if __name__ == "__main__":
    print(r"""
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ██████╗ ███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝      ██╔═══██╗██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗█████╗██║   ██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║╚════╝██║   ██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║      ╚██████╔╝███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ╚═════╝ ╚══════╝

              Native Desktop Mode
    """)

    launch_native_window()
