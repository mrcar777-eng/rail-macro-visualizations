"""
Rail-Landfill Proximity Risk Map
=================================
Interactive Folium map showing NCDOT rail line segments color-coded by their
proximity to NC DEQ active landfills.  Rail crossings and landfill markers are
layered on top with hover popups and cluster grouping.

Risk tiers (distance from each rail segment to its nearest landfill centroid):
  HIGH    < 500 m          red
  MEDIUM  500 m – 2 km    orange
  LOW     2 km – 5 km     yellow
  NONE    > 5 km           green

Distance is approximated in planar meters using a fixed latitude projection
for NC (35.5 °N), accurate to < 1 % for distances below 100 km.

Run from the project root:
    python visualizations/rail_landfill_risk_map.py

Output: rail_landfill_risk_map.html (opens automatically in the default browser)
"""

from __future__ import annotations

import json
import sys
import webbrowser
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.spatial import KDTree

from src.database import get_db_connection

# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

OUTPUT_FILE = Path(__file__).parent.parent / "rail_landfill_risk_map.html"

# ---------------------------------------------------------------------------
# Risk tier definitions: (label, upper_bound_meters, line_color)
# ---------------------------------------------------------------------------

RISK_TIERS: list[tuple[str, float, str]] = [
    ("HIGH",   500.0,        "#d73027"),
    ("MEDIUM", 2_000.0,      "#fc8d59"),
    ("LOW",    5_000.0,      "#fee08b"),
    ("NONE",   float("inf"), "#1a9850"),
]

# Approximate meters-per-degree for NC (35.5 °N)
_DEG_LAT_M = 111_000.0
_DEG_LON_M = _DEG_LAT_M * np.cos(np.radians(35.5))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_meters(lat: float, lon: float) -> tuple[float, float]:
    return lon * _DEG_LON_M, lat * _DEG_LAT_M


def _sample_line_coords(coords: list) -> list[tuple[float, float]]:
    """
    Return a representative set of (lon, lat) points from a LineString or
    MultiLineString coordinate array.  Samples every 5th vertex plus both
    endpoints so that long segments are not mis-scored by a single midpoint.
    """
    # Flatten MultiLineString rings into a single point list
    if coords and isinstance(coords[0][0], (list, tuple)):
        flat: list = [pt for ring in coords for pt in ring]
    else:
        flat = coords

    if not flat:
        return []
    if len(flat) <= 3:
        return [tuple(pt[:2]) for pt in flat]

    sampled = [flat[0]] + flat[1:-1:5] + [flat[-1]]
    return [tuple(pt[:2]) for pt in sampled]


def _tier_for_dist(dist_m: float) -> str:
    for label, threshold, _ in RISK_TIERS:
        if dist_m <= threshold:
            return label
    return "NONE"


def _color_for_tier(tier: str) -> str:
    for label, _, color in RISK_TIERS:
        if label == tier:
            return color
    return "#1a9850"


def _round_coords(coords, decimals: int = 5):
    """Recursively round coordinate arrays to reduce HTML file size."""
    if not coords:
        return coords
    if isinstance(coords[0], (int, float)):
        return [round(v, decimals) for v in coords]
    return [_round_coords(c, decimals) for c in coords]


# ---------------------------------------------------------------------------
# Database fetchers
# ---------------------------------------------------------------------------

def _fetch_rail_lines(conn) -> list[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT objectid, railroad_name, ST_AsGeoJSON(geom) "
            "FROM ncdot_rail_lines"
        )
        return [
            {
                "objectid": row[0],
                "railroad_name": row[1] or "Unknown",
                "geom_json": row[2],
            }
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()


def _geojson_centroid(geom: dict) -> tuple[float, float] | None:
    """
    Return (lat, lon) from a GeoJSON geometry dict.
    GeoJSON coordinates are always [lon, lat], so index [0]=lon, [1]=lat.
    Supports Point, Polygon, MultiPolygon, LineString.
    """
    gtype = geom.get("type", "")
    coords = geom.get("coordinates")
    if not coords:
        return None

    if gtype == "Point":
        return float(coords[1]), float(coords[0])

    if gtype == "LineString":
        mid = coords[len(coords) // 2]
        return float(mid[1]), float(mid[0])

    if gtype == "Polygon":
        ring = coords[0]
    elif gtype == "MultiPolygon":
        ring = [pt for poly in coords for pt in poly[0]]
    else:
        return None

    if not ring:
        return None
    avg_lon = sum(pt[0] for pt in ring) / len(ring)
    avg_lat = sum(pt[1] for pt in ring) / len(ring)
    return float(avg_lat), float(avg_lon)


def _fetch_landfills(conn) -> list[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT objectid, facility_name, county, ST_AsGeoJSON(geom) "
            "FROM ncdeq_active_landfills"
        )
        rows = cursor.fetchall()
    finally:
        cursor.close()

    results = []
    for row in rows:
        geom = json.loads(row[3])
        centroid = _geojson_centroid(geom)
        if centroid is None:
            continue
        lat, lon = centroid
        results.append({
            "objectid": row[0],
            "facility_name": row[1] or "Unknown",
            "county": row[2] or "Unknown",
            "lat": lat,
            "lon": lon,
        })
    return results


def _fetch_crossings(conn) -> list[dict]:
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT crossing_id,
                   street_name,
                   railroad_name,
                   ST_Y(geom) AS lat,
                   ST_X(geom) AS lon
            FROM ncdot_rail_crossings
        """)
        return [
            {
                "crossing_id": row[0],
                "street_name": row[1] or "Unknown",
                "railroad_name": row[2] or "Unknown",
                "lat": float(row[3]),
                "lon": float(row[4]),
            }
            for row in cursor.fetchall()
            if row[3] is not None and row[4] is not None
        ]
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Risk computation
# ---------------------------------------------------------------------------

def compute_risk(rail_lines: list[dict], landfills: list[dict]) -> list[dict]:
    """
    Tag each rail line with its risk tier using a KDTree nearest-neighbor
    search against landfill centroids in approximate planar meters.
    """
    lf_pts = np.array([_to_meters(lf["lat"], lf["lon"]) for lf in landfills])
    tree = KDTree(lf_pts)

    for line in rail_lines:
        geom = json.loads(line["geom_json"])
        samples = _sample_line_coords(geom.get("coordinates", []))

        if not samples:
            line["risk_tier"] = "NONE"
            line["min_dist_m"] = None
            continue

        # (lon, lat) -> (x_m, y_m) for each sampled point
        pts_m = np.array([_to_meters(pt[1], pt[0]) for pt in samples])
        dists, _ = tree.query(pts_m)
        min_dist = float(np.min(dists))

        line["risk_tier"] = _tier_for_dist(min_dist)
        line["min_dist_m"] = round(min_dist)

    return rail_lines


# ---------------------------------------------------------------------------
# GeoJSON builder
# ---------------------------------------------------------------------------

def _build_geojson(rail_lines: list[dict]) -> dict:
    features = []
    for line in rail_lines:
        geom = json.loads(line["geom_json"])
        geom["coordinates"] = _round_coords(geom["coordinates"])
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "objectid": line["objectid"],
                "railroad_name": line["railroad_name"],
                "risk_tier": line["risk_tier"],
                "min_dist_m": line.get("min_dist_m"),
            },
        })
    return {"type": "FeatureCollection", "features": features}


# ---------------------------------------------------------------------------
# Map builder
# ---------------------------------------------------------------------------

def _build_map(
    rail_geojson: dict,
    landfills: list[dict],
    crossings: list[dict],
    tier_counts: Counter,
) -> object:
    import folium
    from folium.plugins import MarkerCluster

    m = folium.Map(
        location=[35.5, -79.0],
        zoom_start=7,
        tiles="CartoDB dark_matter",
    )

    # -- Rail lines ---------------------------------------------------------
    def style_fn(feature):
        tier = feature["properties"]["risk_tier"]
        return {
            "color": _color_for_tier(tier),
            "weight": 3 if tier == "HIGH" else 2,
            "opacity": 0.9 if tier in ("HIGH", "MEDIUM") else 0.7,
        }

    def highlight_fn(_feature):
        return {"color": "#ffffff", "weight": 4, "opacity": 1.0}

    folium.GeoJson(
        rail_geojson,
        name="Rail Lines (risk-colored)",
        style_function=style_fn,
        highlight_function=highlight_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["railroad_name", "risk_tier", "min_dist_m"],
            aliases=["Railroad:", "Risk Tier:", "Nearest landfill (m):"],
            localize=True,
            sticky=False,
        ),
    ).add_to(m)

    # -- Active landfills ---------------------------------------------------
    lf_group = MarkerCluster(name="Active Landfills", show=True)
    for lf in landfills:
        folium.CircleMarker(
            location=[lf["lat"], lf["lon"]],
            radius=5,
            color="#8B4513",
            fill=True,
            fill_color="#A0522D",
            fill_opacity=0.75,
            popup=folium.Popup(
                f"<b>{lf['facility_name']}</b><br>County: {lf['county']}",
                max_width=220,
            ),
        ).add_to(lf_group)
    lf_group.add_to(m)

    # -- Rail crossings (hidden by default; toggle via layer control) --------
    cx_group = MarkerCluster(name="Rail Crossings", show=False)
    for cx in crossings:
        folium.CircleMarker(
            location=[cx["lat"], cx["lon"]],
            radius=3,
            color="#888888",
            fill=True,
            fill_color="#bbbbbb",
            fill_opacity=0.5,
            popup=folium.Popup(
                f"ID: {cx['crossing_id']}<br>"
                f"Street: {cx['street_name']}<br>"
                f"Railroad: {cx['railroad_name']}",
                max_width=220,
            ),
        ).add_to(cx_group)
    cx_group.add_to(m)

    # -- Legend -------------------------------------------------------------
    total = sum(tier_counts.values())
    rows = "".join(
        f'<tr>'
        f'<td><span style="color:{color};font-size:18px;">&#9644;</span></td>'
        f'<td style="padding:0 8px;"><b>{label}</b></td>'
        f'<td style="color:#aaa;">{tier_counts.get(label, 0):,} / {total:,}</td>'
        f'</tr>'
        for label, _, color in RISK_TIERS
    )
    legend_html = f"""
    <div style="
        position:fixed; bottom:40px; left:40px; z-index:9999;
        background:rgba(18,18,18,0.88); padding:14px 18px;
        border-radius:8px; border:1px solid #555;
        font-family:monospace; font-size:13px; color:#eee;
        box-shadow:2px 2px 10px rgba(0,0,0,0.7);
        min-width:230px;
    ">
    <b style="font-size:14px; letter-spacing:0.5px;">
        Rail–Landfill Proximity Risk
    </b>
    <table style="margin-top:10px; border-collapse:collapse; width:100%;">
      <tr style="color:#999;font-size:11px;">
        <td colspan="2">Tier</td>
        <td>Segments</td>
      </tr>
      {rows}
      <tr><td colspan="3" style="padding-top:8px;border-top:1px solid #444;
        color:#999;font-size:11px;">
        &lt;500 m / 500m–2km / 2–5km / &gt;5km
      </td></tr>
    </table>
    <div style="margin-top:10px; border-top:1px solid #444; padding-top:8px;
        color:#aaa; font-size:11px;">
      <span style="color:#A0522D;">&#9679;</span> Active Landfill &nbsp;
      <span style="color:#bbbbbb;">&#9679;</span> Rail Crossing
    </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False, position="topright").add_to(m)

    return m


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    conn = get_db_connection()
    if conn is None:
        print("ERROR: Could not connect to the database.", file=sys.stderr)
        sys.exit(1)

    print("Fetching rail lines...", flush=True)
    rail_lines = _fetch_rail_lines(conn)
    print(f"  {len(rail_lines):,} segments")

    print("Fetching landfill centroids...", flush=True)
    landfills = _fetch_landfills(conn)
    print(f"  {len(landfills):,} landfills")

    print("Fetching rail crossings...", flush=True)
    crossings = _fetch_crossings(conn)
    print(f"  {len(crossings):,} crossings")

    conn.close()

    if not landfills:
        print("WARNING: No landfill data — cannot compute risk.", file=sys.stderr)
        sys.exit(0)

    print("Computing proximity risk...", flush=True)
    rail_lines = compute_risk(rail_lines, landfills)

    tier_counts: Counter = Counter(line["risk_tier"] for line in rail_lines)
    for label, threshold, _ in RISK_TIERS:
        thresh_label = f"< {int(threshold):,} m" if threshold != float("inf") else f"> 5,000 m"
        print(f"  {label:8s} ({thresh_label}): {tier_counts.get(label, 0):,} segments")

    print("Building GeoJSON...", flush=True)
    rail_geojson = _build_geojson(rail_lines)

    print("Rendering map...", flush=True)
    m = _build_map(rail_geojson, landfills, crossings, tier_counts)

    out_path = OUTPUT_FILE.resolve()
    m.save(str(out_path))
    print(f"Saved: {out_path}")
    webbrowser.open(out_path.as_uri())


if __name__ == "__main__":
    main()
