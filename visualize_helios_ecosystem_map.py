#!/usr/bin/env python3
"""Create a visually rich SVG map of Helios oncological, viszeral and uro centers.

The visualization includes per-center metrics:
1) overall partners
2) partners tied to Helios centers but outside Helios hospitals (non-Helios partners)
3) Helios partners not linked to any Helios center (global KPI)
"""

from __future__ import annotations

import argparse
import html
import json
import math
from collections import defaultdict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--centers", default="fulldb_centers.json")
    p.add_argument("--partners", default="fulldb_partners.json")
    p.add_argument("--partner-links", default="fulldb_partners_centers.json")
    p.add_argument("--onco-links", default="fulldb_oncos_centers.json")
    p.add_argument("--visz-links", default="fulldb_viszes_centers.json")
    p.add_argument("--uro-links", default="fulldb_uros_centers.json")
    p.add_argument("--output", default="helios_ecosystem_map.svg")
    return p.parse_args()


def load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_helios_record(record: dict) -> bool:
    haystack = " ".join(
        str(record.get(k, ""))
        for k in ("inst1", "inst2", "basement", "url", "p_email", "specialty")
    ).lower()
    return "helios" in haystack


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def center_short_name(center: dict) -> str:
    raw = center.get("inst1") or center.get("inst2") or f"Center {center.get('id')}"
    return raw if len(raw) <= 56 else raw[:53] + "..."


def cluster_positions(n: int, cx: float, cy: float, base_r: float, spread: float) -> list[tuple[float, float]]:
    if n <= 0:
        return []
    pts: list[tuple[float, float]] = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(n):
        t = i + 1
        radius = base_r + spread * math.sqrt(t / n)
        angle = t * golden
        pts.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return pts


def build_map(args: argparse.Namespace) -> tuple[str, dict]:
    centers = {c["id"]: c for c in load_json(args.centers)}
    partners = {p["id"]: p for p in load_json(args.partners)}
    partner_links = load_json(args.partner_links)

    onco_ids = {r["c_id"] for r in load_json(args.onco_links)}
    visz_ids = {r["c_id"] for r in load_json(args.visz_links)}
    uro_ids = {r["c_id"] for r in load_json(args.uro_links)}

    helios_center_ids_all = {cid for cid, c in centers.items() if is_helios_record(c)}
    typed_helios_ids = {
        cid
        for cid in helios_center_ids_all
        if cid in onco_ids or cid in visz_ids or cid in uro_ids
    }

    center_to_partners: dict[int, set[int]] = defaultdict(set)
    for rel in partner_links:
        pid = rel.get("p_id")
        cid = rel.get("c_id")
        if isinstance(pid, int) and isinstance(cid, int):
            center_to_partners[cid].add(pid)

    helios_partner_ids = {pid for pid, p in partners.items() if is_helios_record(p)}
    helios_linked_partner_ids = {
        pid
        for rel in partner_links
        if rel.get("c_id") in helios_center_ids_all and isinstance((pid := rel.get("p_id")), int)
    }
    helios_partners_not_in_helios_centers = helios_partner_ids - helios_linked_partner_ids

    nodes = []
    for cid in sorted(typed_helios_ids):
        c = centers[cid]
        pids = center_to_partners.get(cid, set())
        partner_rows = [partners[pid] for pid in pids if pid in partners]
        non_helios = sum(1 for p in partner_rows if not is_helios_record(p))
        helios = sum(1 for p in partner_rows if is_helios_record(p))
        center_types = []
        if cid in onco_ids:
            center_types.append("onco")
        if cid in visz_ids:
            center_types.append("visz")
        if cid in uro_ids:
            center_types.append("uro")
        primary = ("onco" if "onco" in center_types else "visz" if "visz" in center_types else "uro")
        nodes.append(
            {
                "id": cid,
                "name": center_short_name(c),
                "loc": c.get("loc", ""),
                "types": center_types,
                "primary": primary,
                "overall": len(pids),
                "external": non_helios,
                "helios_inside": helios,
            }
        )

    by_cluster = {"onco": [], "visz": [], "uro": []}
    for n in nodes:
        by_cluster[n["primary"]].append(n)

    palette = {"onco": "#8e44ad", "visz": "#16a085", "uro": "#e67e22"}

    w, h = 2400, 1500
    clusters = {
        "onco": (600, 760, 80, 430),
        "visz": (1200, 760, 80, 430),
        "uro": (1800, 760, 80, 430),
    }

    out = []
    out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">')
    out.append(
        "<style>"
        "text{font-family:Inter,Segoe UI,Arial,sans-serif;}"
        ".title{font-size:38px;font-weight:700;}"
        ".subtitle{font-size:18px;fill:#444;}"
        ".kpiLabel{font-size:16px;fill:#555;}"
        ".kpiValue{font-size:34px;font-weight:700;}"
        ".clusterTitle{font-size:28px;font-weight:700;}"
        ".small{font-size:13px;fill:#555;}"
        "</style>"
    )
    out.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f8fafc"/>')
    out.append('<text class="title" x="60" y="62">Helios Center Ecosystem Map (Onko + VISZ + Uro)</text>')
    out.append('<text class="subtitle" x="60" y="92">Node size = overall partners · Ring width = external (non-Helios) partners · Fill color = center category</text>')

    kpis = [
        ("Helios centers (Onko/VISZ/Uro)", f"{len(nodes)}"),
        ("Partner links across those centers", f"{sum(n['overall'] for n in nodes):,}"),
        ("External partners in Helios centers", f"{sum(n['external'] for n in nodes):,}"),
        ("Helios partners not in any Helios center", f"{len(helios_partners_not_in_helios_centers):,}"),
    ]
    for i, (label, value) in enumerate(kpis):
        x = 60 + i * 560
        out.append(f'<rect x="{x}" y="118" width="520" height="128" rx="14" fill="#ffffff" stroke="#dfe6ee"/>')
        out.append(f'<text class="kpiLabel" x="{x+20}" y="156">{esc(label)}</text>')
        out.append(f'<text class="kpiValue" x="{x+20}" y="210">{esc(value)}</text>')

    for cluster, (cx, cy, base, spread) in clusters.items():
        fill = palette[cluster]
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{spread+120}" fill="{fill}" opacity="0.05"/>')
        out.append(f'<text class="clusterTitle" x="{cx}" y="330" text-anchor="middle" fill="{fill}">{cluster.upper()} Centers</text>')

        items = sorted(by_cluster[cluster], key=lambda x: x["overall"], reverse=True)
        coords = cluster_positions(len(items), cx, cy, base, spread)
        for idx, (node, (x, y)) in enumerate(zip(items, coords), start=1):
            r = 10 + min(52, math.sqrt(max(node["overall"], 1)) * 1.45)
            ext_ratio = node["external"] / node["overall"] if node["overall"] else 0
            ring_w = 1.5 + 8 * ext_ratio
            opacity = 0.38 + 0.45 * ext_ratio
            types_label = "/".join(t.upper() for t in node["types"])
            tooltip = (
                f"{node['name']} ({node['loc']})\\n"
                f"Types: {types_label}\\n"
                f"Overall partners: {node['overall']}\\n"
                f"External partners (non-Helios): {node['external']}\\n"
                f"Helios partners inside center: {node['helios_inside']}"
            )
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" opacity="{opacity:.2f}" '
                f'stroke="#1f2937" stroke-width="{ring_w:.2f}"><title>{esc(tooltip)}</title></circle>'
            )
            if idx <= 18:
                out.append(
                    f'<text class="small" x="{x:.1f}" y="{y+r+16:.1f}" text-anchor="middle">'
                    f"{esc(node['name'])}</text>"
                )

    top = sorted(nodes, key=lambda n: n["overall"], reverse=True)[:18]
    out.append('<rect x="60" y="1240" width="2280" height="220" rx="14" fill="#ffffff" stroke="#dfe6ee"/>')
    out.append('<text x="80" y="1270" style="font-size:22px;font-weight:700;">Top Helios centers by partner count</text>')
    for i, n in enumerate(top):
        col = i // 6
        row = i % 6
        x = 80 + col * 760
        y = 1305 + row * 24
        out.append(
            f'<text class="small" x="{x}" y="{y}">{i+1:02d}. {esc(n["name"])} '
            f'| overall: {n["overall"]} | external: {n["external"]} | helios-inside: {n["helios_inside"]}</text>'
        )

    out.append("</svg>")

    metrics = {
        "center_count": len(nodes),
        "overall_partner_links": sum(n["overall"] for n in nodes),
        "external_partner_links": sum(n["external"] for n in nodes),
        "helios_partners_not_in_helios_centers": len(helios_partners_not_in_helios_centers),
    }
    return "\n".join(out), metrics


def main() -> None:
    args = parse_args()
    svg, metrics = build_map(args)
    out_path = Path(args.output)
    out_path.write_text(svg, encoding="utf-8")
    print(f"Saved visualization to: {out_path}")
    for k, v in metrics.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
