from __future__ import annotations

import argparse
from pathlib import Path

from soccer_env.web_viewer import ViewerData, load_replay, serve_viewer

BASE_DIRECTORY = Path(__file__).resolve().parent


def newest_replay() -> Path | None:
    log_directory = BASE_DIRECTORY / "logs"
    candidates = list(log_directory.rglob("*.jsonl")) if log_directory.exists() else []
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Play and inspect an AI Soccer Arena replay in a browser")
    parser.add_argument("replay", nargs="?", help="JSONL path; defaults to the newest replay")
    parser.add_argument("--port", type=int, default=0, help="Local port; zero chooses an available port")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL without opening it")
    args = parser.parse_args()
    replay = Path(args.replay).resolve() if args.replay else newest_replay()
    if replay is None:
        raise SystemExit("No replay found. Run python organizers/run_match.py first, or provide a JSONL path.")
    metadata, frames = load_replay(replay)
    metadata = {**metadata, "replay_path": str(replay.resolve())}
    print(f"Loaded {len(frames)} frames from {replay}")
    serve_viewer(ViewerData("replay", metadata, frames), args.port, not args.no_browser)


if __name__ == "__main__":
    main()
