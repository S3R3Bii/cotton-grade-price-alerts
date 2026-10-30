"""Capture three fixed public workbooks once; never modify or replace originals."""

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-dir", type=Path, required=True)
    args = parser.parse_args()
    args.private_dir.mkdir(parents=True, exist_ok=False)
    commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    receipts = []
    for request in json.loads(
        (ROOT / "data/source_requests.json").read_text(encoding="utf-8")
    ):
        started = datetime.now(timezone.utc).isoformat()
        body, status, headers, error = b"", None, {}, None
        try:
            with urlopen(
                Request(
                    request["url"],
                    headers={"User-Agent": "IndependentCottonQuoteResearch/1.0"},
                ),
                timeout=120,
            ) as response:
                status, headers, body = (
                    response.status,
                    dict(response.headers.items()),
                    response.read(),
                )
        except HTTPError as exc:
            status, headers, body, error = (
                exc.code,
                dict(exc.headers.items()),
                exc.read(),
                str(exc),
            )
        except Exception as exc:
            error = type(exc).__name__ + ": " + str(exc)
        (args.private_dir / request["file"]).write_bytes(body)
        item = dict(
            request,
            started_utc=started,
            completed_utc=datetime.now(timezone.utc).isoformat(),
            status=status,
            headers={
                k: v
                for k, v in headers.items()
                if k.lower()
                in {"content-type", "content-length", "last-modified", "etag", "date"}
            },
            bytes=len(body),
            sha256=hashlib.sha256(body).hexdigest(),
            protocol_commit=commit,
            python=platform.python_version(),
            error=error,
        )
        receipts.append(item)
        (args.private_dir / "requests.json").write_text(
            json.dumps(receipts, indent=2) + "\n", encoding="utf-8"
        )
        print(
            json.dumps(
                {k: item[k] for k in ["marketing_year", "status", "bytes", "error"]}
            ),
            flush=True,
        )
        assert (
            status == 200 and error is None
        ), "Source failure preserved; stop without bypass or silent retry"
    print("CAPTURE_COMPLETE", len(receipts), flush=True)


if __name__ == "__main__":
    main()
