"""run_all — execute the ETL pipeline in dependency order (Calc-Spec §3).

    00_init_db -> 00b_prepare_data -> 01 -> 02 -> 03 -> 04 -> 05_validate

Numbered scripts have non-identifier names, so they are loaded by path via runpy
rather than imported. Run inside the api container:

    docker compose exec api python scripts/run_all.py
"""

from __future__ import annotations

import pathlib
import runpy
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # backend root for `import app...`

STEPS = [
    "00_init_db.py",
    "00b_prepare_data.py",
    "01_load_sessions.py",
    "02_load_market.py",
    "03_build_pool.py",
    "04_build_profile.py",
    "05_validate.py",
]


def main() -> None:
    for step in STEPS:
        print(f"\n{'=' * 60}\n>>> {step}\n{'=' * 60}")
        runpy.run_path(str(HERE / step), run_name="__main__")
    print("\nrun_all: pipeline complete.")


if __name__ == "__main__":
    main()
