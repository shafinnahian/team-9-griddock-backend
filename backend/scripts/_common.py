"""Shared ETL helpers (parsing rules fixed by Calc-Spec §0; idempotent writes)."""

from __future__ import annotations

import glob
import os
import pathlib
import sys

import pandas as pd
from sqlalchemy import text


def bootstrap_path() -> None:
    """Add the backend root (parent of app/ and scripts/) to sys.path so scripts
    run as files (`python scripts/0X_*.py`) can `import app...`."""
    root = str(pathlib.Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


bootstrap_path()

from app.core.config import settings  # noqa: E402

# SMARD CSV parsing conventions (Calc-Spec §0) — do not change.
SMARD_READ_KW = dict(
    sep=";", thousands=",", decimal=".", na_values=["-"], encoding="utf-8-sig"
)
SMARD_DATE_FMT = "%b %d, %Y %I:%M %p"  # e.g. "Jan 1, 2024 12:00 AM"


def find_file(pattern: str) -> str:
    """Resolve a single data file by glob within DATA_DIR; fail clearly if absent."""
    matches = sorted(glob.glob(os.path.join(settings.data_dir, pattern)))
    if not matches:
        raise FileNotFoundError(
            f"No file matching {pattern!r} in {settings.data_dir!r}"
        )
    return matches[0]


def _match_col(df: pd.DataFrame, needle: str) -> str:
    """Return the first column whose name contains `needle` (case-insensitive).

    SMARD headers carry suffixes like 'grid load [MWh] Original resolutions'.
    """
    low = needle.lower()
    for c in df.columns:
        if low in c.lower():
            return c
    raise KeyError(f"No column containing {needle!r} in {list(df.columns)}")


def read_smard(pattern: str, columns: dict[str, str]) -> pd.DataFrame:
    """Read a SMARD export and return ['ts'] + renamed numeric columns.

    `columns` maps an output name -> a substring to locate in the header.
    """
    df = pd.read_csv(find_file(pattern), **SMARD_READ_KW)
    start_col = _match_col(df, "Start date")
    out = pd.DataFrame()
    out["ts"] = pd.to_datetime(df[start_col], format=SMARD_DATE_FMT)
    for out_name, needle in columns.items():
        out[out_name] = pd.to_numeric(df[_match_col(df, needle)], errors="coerce")
    return out


def truncate_then_insert(table: str, df: pd.DataFrame) -> int:
    """Idempotent load: TRUNCATE then bulk-insert `df` into `table`.

    Imported lazily so this module is usable without a live DB (e.g. 00b prep).
    """
    from app.db import engine

    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {table}"))
    df.to_sql(table, engine, if_exists="append", index=False, method="multi", chunksize=1000)
    return len(df)
