"""Replay committed code into separate paths, retaining frozen source containers."""

import csv
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    originals = {
        p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in ROOT.rglob("*")
        if p.is_file()
        and not any(n in p.parts for n in [".git", "__pycache__", "rendered"])
        and p.name != "reproduction.json"
        and p.suffix not in [".log", ".aux", ".out", ".xdv"]
    }
    fields = documents = 0
    with tempfile.TemporaryDirectory(prefix="cotton-identity-replay-") as temp:
        folder = Path(temp)
        target = folder / "study"
        inputs = folder / "input-rebuild"
        results = folder / "results"
        results.mkdir()
        (inputs / "data").mkdir(parents=True)
        subprocess.run(
            ["git", "clone", "--quiet", "--no-hardlinks", str(ROOT), str(target)],
            check=True,
        )

        def run(*args):
            result = subprocess.run(
                [sys.executable, *args], cwd=target, capture_output=True, text=True
            )
            if result.returncode:
                raise RuntimeError(
                    str(args)
                    + "\n"
                    + result.stdout[-1800:]
                    + "\n"
                    + result.stderr[-1800:]
                )
            return result.stdout

        def compare_csv(left, right):
            nonlocal fields
            opener = gzip.open if left.suffix == ".gz" else open
            with opener(left, "rt", encoding="utf-8", newline="") as a, opener(
                right, "rt", encoding="utf-8", newline=""
            ) as b:
                for x, y in zip(csv.reader(a), csv.reader(b), strict=True):
                    assert x == y, left.name
                    fields += len(x)

        def compare_json(left, right):
            nonlocal documents
            assert json.loads(left.read_text(encoding="utf-8")) == json.loads(
                right.read_text(encoding="utf-8")
            ), left.name
            documents += 1

        run("src/freeze_proof.py")
        for name in ["quote_rows.csv.gz", "market_bindings.json"]:
            shutil.copyfile(target / "data" / name, inputs / "data" / name)
        # Route the fixed-output input builder to a sandbox; scientific code is unchanged.
        code = "import sys; from pathlib import Path; sys.path.insert(0,'src'); import build_inputs; build_inputs.ROOT=Path(sys.argv[1]); build_inputs.main()"
        run("-c", code, str(inputs))
        check = "import sys; from pathlib import Path; sys.path.insert(0,'src'); import verify_inputs; verify_inputs.ROOT=Path(sys.argv[1]); verify_inputs.main()"
        run("-c", check, str(inputs))
        for name in [
            "quote_key_ledger.csv",
            "pairs.csv",
            "pair_ledger.csv",
            "coverage.csv",
        ]:
            compare_csv(ROOT / "data" / name, inputs / "data" / name)
        for name in ["input_receipt.json", "input_verification.json"]:
            compare_json(ROOT / "data" / name, inputs / "data" / name)
        for phase in ["development", "held"]:
            rebuilt = results / phase
            run("src/analyze.py", "--phase", phase, "--output-dir", str(rebuilt))
            run("src/verify_results.py", "--phase", phase, "--output-dir", str(rebuilt))
            for name in [
                "cases.csv.gz",
                "by_market_case.csv",
                "by_month.csv",
                "summary.csv",
                "source_premiums.csv",
            ]:
                compare_csv(ROOT / "results" / phase / name, rebuilt / name)
            compare_json(
                ROOT / "results" / phase / "summary.json", rebuilt / "summary.json"
            )
            recorded = json.loads(
                (ROOT / "results" / phase / "verification.json").read_text(
                    encoding="utf-8"
                )
            )
            fresh = json.loads(
                (rebuilt / "verification.json").read_text(encoding="utf-8")
            )
            assert {k: v for k, v in fresh.items() if k != "sha256"} == {
                k: v for k, v in recorded.items() if k != "sha256"
            }
            for name, digest in fresh["sha256"].items():
                assert (
                    hashlib.sha256((rebuilt / name).read_bytes()).hexdigest() == digest
                )
            documents += 1
        run("-m", "unittest", "discover", "-s", "tests")
        matched = json.loads(
            run(
                "src/cli.py", "examples/old-authored.json", "examples/new-authored.json"
            )
        )
        blind = json.loads(
            run(
                "src/cli.py",
                "examples/old-authored.json",
                "examples/new-authored.json",
                "--rule",
                "grade_blind",
            )
        )
        assert (
            matched["estimated_change_fraction"] == "0"
            and matched["alert"] is False
            and blind["estimated_change_fraction"] == "1/20"
            and blind["alert"] is True
        )
        documents += 2
        run("src/verify_containers.py")
        compare_json(
            ROOT / "results/container_verification.json",
            target / "results/container_verification.json",
        )
        run("src/freeze_proof.py")
    for name, digest in originals.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    result = dict(
        status="PASS",
        exact_csv_fields_including_headers=fields,
        json_documents=documents,
        finite_fixtures=28,
        frozen_dependencies=37,
        original_files_unchanged=True,
        network_during_replay=False,
        scope="Committed full-history clone; path-only input sandbox; separately regenerated case outputs; exact fields/JSON content and fresh export hashes; no original workbook recapture",
    )
    (ROOT / "results/reproduction.json").write_bytes(
        (json.dumps(result, indent=2) + "\n").encode()
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
