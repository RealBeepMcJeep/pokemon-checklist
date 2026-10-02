#!/usr/bin/env python3
"""Explicit offline release build. Cargo outputs live in the private retained cache."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from story_native import build_directory


def main():
    cargo = shutil.which("cargo")
    if cargo is None:
        candidate = Path.home() / ".cargo/bin/cargo"
        if not candidate.exists():
            candidate = Path("/opt/data/home/.cargo/bin/cargo")
        cargo = str(candidate)
    target = build_directory()
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    env = dict(os.environ)
    # Portable baseline x86 code; ignore caller-specific CPU features.
    env["RUSTFLAGS"] = "-C target-cpu=x86-64"
    env["PATH"] = str(Path(cargo).parent) + os.pathsep + env.get("PATH", "")
    subprocess.run([cargo, "build", "--offline", "--release", "--manifest-path",
                    str(Path(__file__).with_name("Cargo.toml")), "--target-dir", str(target)],
                   env=env, check=True)
    print(target / "release/story-search")


if __name__ == "__main__":
    main()
