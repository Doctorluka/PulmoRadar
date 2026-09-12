from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import load_config, project_root
from .pipeline import run_topic


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PulmoRadar weekly pulmonary literature radar")
    parser.add_argument("command", choices=["run"], help="run a digest")
    parser.add_argument("--topic", required=True, choices=["monday", "thursday", "copd", "fibrosis", "pah"])
    parser.add_argument("--send", action="store_true", help="send email and record history")
    parser.add_argument("--dry-run", action="store_true", help="skip LLM/email; heuristic ranking only")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    _load_dotenv(project_root() / ".env")
    cfg = load_config(args.config)
    try:
        result = run_topic(args.topic, cfg, send=args.send, dry_run=args.dry_run)
    except Exception as exc:
        if args.send and not args.dry_run:
            try:
                from .emailer import send_email

                send_email(
                    cfg,
                    f"PulmoRadar 运行失败 · {args.topic}",
                    f"<p>本次 {args.topic} 周报失败，请查看 Actions / 本地日志。错误类型：{type(exc).__name__}</p>",
                )
            except Exception:
                pass
        raise
    print(result["subject"])
    for note in result["notes"]:
        print(note)
    print(f"published: {len(result['published'])}")
    print(f"preprints: {len(result['preprints'])}")
    print(f"archive: {result['archive_md']}")
    if result["sent"]:
        print("email: sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
