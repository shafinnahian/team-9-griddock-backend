"""00b — convert the markdown sessions table to a CSV the ETL can read.

The supply source ships as a markdown table (data/source/nml_ev_sessions.md).
This step materialises it as data/NML_ev_sessions.csv (idempotent).

    python scripts/00b_prepare_data.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

from app.core.config import settings  # noqa: E402


def parse_markdown_table(path: str) -> pd.DataFrame:
    rows: list[list[str]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.lstrip().startswith("|"):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            rows.append(cells)
    if len(rows) < 2:
        raise ValueError(f"No markdown table rows found in {path!r}")
    header = rows[0]
    # rows[1] is the |---|---| separator; data starts at rows[2]
    data = [r for r in rows[2:] if len(r) == len(header)]
    return pd.DataFrame(data, columns=header)


def main() -> None:
    src = settings.sessions_md_path
    dst = settings.sessions_csv_path
    df = parse_markdown_table(src)
    df.to_csv(dst, index=False)
    print(f"00b: wrote {len(df)} session rows -> {dst}")
    if len(df) != 8000:
        print(f"  WARNING: expected 8000 rows, got {len(df)}")


if __name__ == "__main__":
    main()
