"""Geography service — F8 regional / postal distribution of the V2G-able fleet."""

from __future__ import annotations

from app.cache import cache
from app.core import params


def _region(postal_code: int) -> str:
    pc = str(postal_code)
    for region, prefixes in params.REGION_PREFIXES.items():
        if pc.startswith(prefixes):
            return region
    return params.REGION_OTHER


def get_geography(top_n: int = 10) -> dict:
    v2g = cache.sessions[cache.sessions["is_v2g_able"]].copy()
    total_sessions = len(v2g)
    v2g["region"] = v2g["postal_code"].apply(_region)

    region_order = list(params.REGION_PREFIXES.keys()) + [params.REGION_OTHER]
    regions = []
    for region in region_order:
        g = v2g[v2g["region"] == region]
        regions.append(
            {
                "region": region,
                "sessions": int(len(g)),
                "vehicles": int(g["vehicle_id"].nunique()),
                "kw": round(float(g["peak_kw"].sum()), 1),
                "share": round(len(g) / total_sessions, 3) if total_sessions else 0.0,
            }
        )

    top = (
        v2g.groupby("postal_code")
        .agg(sessions=("session_id", "size"),
             vehicles=("vehicle_id", "nunique"),
             kw=("peak_kw", "sum"))
        .reset_index()
        .sort_values("sessions", ascending=False)
        .head(top_n)
    )
    top_postal_codes = [
        {
            "postal_code": int(r.postal_code),
            "sessions": int(r.sessions),
            "vehicles": int(r.vehicles),
            "kw": round(float(r.kw), 1),
        }
        for r in top.itertuples(index=False)
    ]

    return {"regions": regions, "top_postal_codes": top_postal_codes}
