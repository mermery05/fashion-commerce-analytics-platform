"""Download the source dataset from Kaggle into data/raw/.

Uses the modern Kaggle API token (KGAT_...) stored at ~/.kaggle/access_token,
or the KAGGLE_API_TOKEN environment variable. Falls back to a synthetic
sample generator if the download fails, so CI and local dev can still run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


DATASET_SLUG = "bytadit/transactional-ecommerce"
RAW_DIR = Path("data/raw")
SAMPLE_DIR = Path("data/sample")


def _ensure_auth() -> None:
    """Check that a Kaggle credential is available. Raise if not."""
    token_file = Path.home() / ".kaggle" / "access_token"
    env_token = os.environ.get("KAGGLE_API_TOKEN")

    if not (token_file.exists() or env_token):
        sys.exit(
            "ERROR: No Kaggle credential found.\n"
            "  Create one at https://www.kaggle.com/settings -> API -> Create New Token\n"
            "  Then either:\n"
            f"    - Save it to {token_file}\n"
            "    - Or export KAGGLE_API_TOKEN=KGAT_... in your shell"
        )


def download_from_kaggle() -> None:
    """Run the Kaggle CLI to fetch and unzip the dataset."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_auth()

    cmd = [
        "kaggle",
        "datasets",
        "download",
        "-d",
        DATASET_SLUG,
        "-p",
        str(RAW_DIR),
        "--unzip",
    ]
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)
    print(f"Downloaded to {RAW_DIR.resolve()}")


def fallback_to_sample() -> None:
    """If the real download fails, copy a synthetic sample into data/raw/."""
    if not SAMPLE_DIR.exists():
        sys.exit(
            f"ERROR: Download failed and no sample found at {SAMPLE_DIR}.\n"
            "Create a synthetic sample first, or fix your Kaggle credentials."
        )
    print(f"Falling back to synthetic sample in {SAMPLE_DIR}...")
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for src in SAMPLE_DIR.glob("*.csv"):
        dst = RAW_DIR / src.name
        dst.write_bytes(src.read_bytes())
        print(f"  copied {src.name} -> {dst}")


def main() -> None:
    try:
        download_from_kaggle()
    except subprocess.CalledProcessError as e:
        print(f"Kaggle download failed (exit {e.returncode}).")
        fallback_to_sample()
    except SystemExit:
        raise


if __name__ == "__main__":
    main()