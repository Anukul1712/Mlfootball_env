from __future__ import annotations

import argparse
from pathlib import Path

from soccer_env.web_viewer import ViewerData, load_replay, serve_viewer


BASE_DIRECTORY = Path(__file__).resolve().parent


def newest_replay() -> Path | None:
    candidates = list((BASE_DIRECTORY / "logs").rglob("*.jsonl")) if (BASE_DIRECTORY / "logs").exists() else []
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect a participant practice replay in a browser")
    parser.add_argument("replay", nargs="?", help="JSONL path; defaults to newest participant replay")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    replay = Path(args.replay).resolve() if args.replay else newest_replay()
    if replay is None:
        raise SystemExit("No replay found. Run: python run_match.py")
    metadata, frames = load_replay(replay)
    metadata = {**metadata, "replay_path": str(replay)}
    print(f"Loaded {len(frames)} frames from {replay}")
    serve_viewer(ViewerData("replay", metadata, frames), args.port, not args.no_browser)


if __name__ == "__main__":
    main()
