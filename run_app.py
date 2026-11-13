"""Start the JobHunter app:  python run_app.py   (opens http://127.0.0.1:8765 in your browser)."""
import argparse
import threading
import webbrowser
from pathlib import Path

from jobhunter_ui.server import make_server


def main() -> None:
    ap = argparse.ArgumentParser(description="JobHunter local app")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    srv = make_server(Path(__file__).resolve().parent, "127.0.0.1", a.port)
    url = f"http://127.0.0.1:{a.port}"
    print(f"JobHunter is running at {url}  (press Ctrl+C to stop; only this computer can open it)")
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        srv.runner.stop()


if __name__ == "__main__":
    main()
