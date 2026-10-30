"""Distinguish as-run export hashes from canonical Git text without changing either."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    phases = []
    for phase in ["development", "held"]:
        directory = ROOT / "results" / phase
        receipt = json.loads(
            (directory / "verification.json").read_text(encoding="utf-8")
        )
        files = []
        for name, recorded in receipt["sha256"].items():
            data = (directory / name).read_bytes()
            current = hashlib.sha256(data).hexdigest()
            state = "exact_runtime_bytes"
            if current != recorded:
                assert name.endswith(".json"), (
                    "Unexpected changed non-JSON export",
                    phase,
                    name,
                )
                canonical = data.replace(b"\r\n", b"\n")
                windows = canonical.replace(b"\n", b"\r\n")
                assert recorded in {
                    hashlib.sha256(canonical).hexdigest(),
                    hashlib.sha256(windows).hexdigest(),
                }, ("Export content changed", phase, name)
                assert json.loads(canonical) == json.loads(windows)
                state = "JSON_line_endings_only_runtime_hash_retained"
            files.append(
                dict(
                    file=name,
                    recorded_runtime_sha256=recorded,
                    current_canonical_sha256=current,
                    status=state,
                )
            )
        phases.append(dict(phase=phase, status="pass", files=files))
    result = dict(
        status="pass",
        scope="Original numerical receipts retained; current byte hashes separated from as-run JSON line endings",
        phases=phases,
    )
    (ROOT / "results/container_verification.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(
        json.dumps(
            {
                "status": "pass",
                "files_checked": sum(len(p["files"]) for p in phases),
                "line_ending_only": sum(
                    f["status"].startswith("JSON") for p in phases for f in p["files"]
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
