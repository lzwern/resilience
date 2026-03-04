#!/usr/bin/env python3
"""Erstellt eine visuell komplexe SVG-Karte für Helios ONKO/VISZ/URO-Zentren.

Die Struktur basiert auf den Entitäten aus:
- fulldb_oncos.json
- fulldb_viszes.json
- fulldb_uros.json

Metriken je Zentrum:
1) Gesamtzahl angebundener Partner
2) Nicht-Helios-Partner innerhalb angebundener Helios-Zentren
3) Helios-Partner, die in keinem Helios-Zentrum angebunden sind (global)
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
    p.add_argument("--oncos", default="fulldb_oncos.json")
    p.add_argument("--viszes", default="fulldb_viszes.json")
    p.add_argument("--uros", default="fulldb_uros.json")
    p.add_argument("--onco-links", default="fulldb_oncos_centers.json")
    p.add_argument("--visz-links", default="fulldb_viszes_centers.json")
    p.add_argument("--uro-links", default="fulldb_uros_centers.json")
    p.add_argument("--output", default="helios_ecosystem_map.svg")
    return p.parse_args()


def load_json(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def is_helios(record: dict) -> bool:
    text = " ".join(
        str(record.get(k, ""))
        for k in ("inst1", "inst2", "basement", "url", "p_email", "specialty")
    ).lower()
    return "helios" in text


def esc(text: str) -> str:
    return html.escape(text, quote=True)


def short_name(text: str, max_len: int = 60) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def spiral_positions(n: int, cx: float, cy: float, base_r: float, spread: float) -> list[tuple[float, float]]:
    if n <= 0:
        return []
    coords: list[tuple[float, float]] = []
    golden = math.pi * (3 - math.sqrt(5))
    for i in range(1, n + 1):
        r = base_r + spread * math.sqrt(i / n)
        a = golden * i
        coords.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return coords


def collect_domain_nodes(domain_name: str, nodes_raw: list[dict], links: list[dict], centers: dict[int, dict], center_to_partners: dict[int, set[int]], partners: dict[int, dict]) -> list[dict]:
    helios_nodes = [n for n in nodes_raw if is_helios(n)]
    node_by_id = {n["id"]: n for n in helios_nodes}

    node_to_centers: dict[int, set[int]] = defaultdict(set)
    for rel in links:
        nid = rel.get("n_id")
        cid = rel.get("c_id")
        if isinstance(nid, int) and isinstance(cid, int) and nid in node_by_id:
            node_to_centers[nid].add(cid)

    result = []
    for nid, node in node_by_id.items():
        cids = node_to_centers.get(nid, set())
        partner_ids: set[int] = set()
        for cid in cids:
            partner_ids.update(center_to_partners.get(cid, set()))
        partner_rows = [partners[pid] for pid in partner_ids if pid in partners]
        non_helios_count = sum(1 for p in partner_rows if not is_helios(p))
        helios_inside_count = sum(1 for p in partner_rows if is_helios(p))

        result.append(
            {
                "domain": domain_name,
                "id": nid,
                "name": short_name(node.get("inst1") or node.get("inst2") or f"Zentrum {nid}"),
                "ort": node.get("loc", ""),
                "center_count": len(cids),
                "partner_gesamt": len(partner_ids),
                "partner_extern": non_helios_count,
                "partner_helios_intern": helios_inside_count,
            }
        )
    return sorted(result, key=lambda x: x["partner_gesamt"], reverse=True)


def build_map(args: argparse.Namespace) -> tuple[str, dict]:
    centers = {c["id"]: c for c in load_json(args.centers)}
    partners = {p["id"]: p for p in load_json(args.partners)}
    partner_links = load_json(args.partner_links)

    center_to_partners: dict[int, set[int]] = defaultdict(set)
    for rel in partner_links:
        pid = rel.get("p_id")
        cid = rel.get("c_id")
        if isinstance(pid, int) and isinstance(cid, int):
            center_to_partners[cid].add(pid)

    helios_center_ids = {cid for cid, c in centers.items() if is_helios(c)}
    helios_partner_ids = {pid for pid, p in partners.items() if is_helios(p)}
    helios_partner_linked_to_helios_center = {
        rel["p_id"]
        for rel in partner_links
        if isinstance(rel.get("p_id"), int)
        and isinstance(rel.get("c_id"), int)
        and rel["c_id"] in helios_center_ids
    }
    helios_partner_ohne_zentrum = helios_partner_ids - helios_partner_linked_to_helios_center

    onco_nodes = collect_domain_nodes(
        "Onkologische Zentren",
        load_json(args.oncos),
        load_json(args.onco_links),
        centers,
        center_to_partners,
        partners,
    )
    visz_nodes = collect_domain_nodes(
        "Viszeralonkologische Zentren",
        load_json(args.viszes),
        load_json(args.visz_links),
        centers,
        center_to_partners,
        partners,
    )
    uro_nodes = collect_domain_nodes(
        "Uroonkologische Zentren",
        load_json(args.uros),
        load_json(args.uro_links),
        centers,
        center_to_partners,
        partners,
    )

    all_nodes = onco_nodes + visz_nodes + uro_nodes

    colors = {
        "Onkologische Zentren": "#8e44ad",
        "Viszeralonkologische Zentren": "#16a085",
        "Uroonkologische Zentren": "#e67e22",
    }
    domains = [
        ("Onkologische Zentren", onco_nodes, (600, 820, 70, 380)),
        ("Viszeralonkologische Zentren", visz_nodes, (1200, 820, 70, 380)),
        ("Uroonkologische Zentren", uro_nodes, (1800, 820, 70, 380)),
    ]

    w, h = 2400, 1600
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">']
    out.append(
        "<style>"
        "text{font-family:Inter,Segoe UI,Arial,sans-serif;}"
        ".title{font-size:40px;font-weight:700;}"
        ".subtitle{font-size:18px;fill:#475569;}"
        ".kpiL{font-size:16px;fill:#64748b;}"
        ".kpiV{font-size:34px;font-weight:700;fill:#0f172a;}"
        ".cluster{font-size:28px;font-weight:700;}"
        ".small{font-size:12px;fill:#334155;}"
        "</style>"
    )
    out.append(f'<rect x="0" y="0" width="{w}" height="{h}" fill="#f8fafc"/>')
    out.append('<text class="title" x="60" y="64">Helios-Landkarte: ONKO / VISZ / URO</text>')
    out.append('<text class="subtitle" x="60" y="94">Struktur nach Onkologischen, Viszeralonkologischen und Uroonkologischen Zentren</text>')
    out.append('<text class="subtitle" x="60" y="120">Kreisgröße = Partner gesamt · Randstärke = Anteil externe Partner (nicht Helios)</text>')

    kpis = [
        ("Helios Onkologische Zentren", str(len(onco_nodes))),
        ("Helios VISZ-Zentren", str(len(visz_nodes))),
        ("Helios URO-Zentren", str(len(uro_nodes))),
        ("Helios-Partner ohne Helios-Zentrum", f"{len(helios_partner_ohne_zentrum):,}"),
    ]
    for i, (lab, val) in enumerate(kpis):
        x = 60 + i * 560
        out.append(f'<rect x="{x}" y="150" width="520" height="122" rx="14" fill="#fff" stroke="#dbe3ee"/>')
        out.append(f'<text class="kpiL" x="{x+20}" y="188">{esc(lab)}</text>')
        out.append(f'<text class="kpiV" x="{x+20}" y="238">{esc(val)}</text>')

    for dname, nodes, (cx, cy, base, spread) in domains:
        color = colors[dname]
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{spread+120}" fill="{color}" opacity="0.06"/>')
        out.append(f'<text class="cluster" x="{cx}" y="340" text-anchor="middle" fill="{color}">{esc(dname)}</text>')

        coords = spiral_positions(len(nodes), cx, cy, base, spread)
        for idx, (n, (x, y)) in enumerate(zip(nodes, coords), start=1):
            total = max(n["partner_gesamt"], 1)
            ext_ratio = n["partner_extern"] / total
            radius = 10 + min(54, math.sqrt(total) * 1.55)
            stroke_w = 1.8 + 8.5 * ext_ratio
            opacity = 0.35 + 0.5 * ext_ratio

            tooltip = (
                f"{n['name']} ({n['ort']})\\n"
                f"Kategorie: {n['domain']}\\n"
                f"Angebundene Organzentren: {n['center_count']}\\n"
                f"Partner gesamt: {n['partner_gesamt']}\\n"
                f"Partner extern (nicht Helios): {n['partner_extern']}\\n"
                f"Partner Helios-intern: {n['partner_helios_intern']}"
            )
            out.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" opacity="{opacity:.2f}" '
                f'stroke="#1f2937" stroke-width="{stroke_w:.2f}"><title>{esc(tooltip)}</title></circle>'
            )
            if idx <= 10:
                out.append(f'<text class="small" x="{x:.1f}" y="{y+radius+15:.1f}" text-anchor="middle">{esc(n["name"])}</text>')

    top = sorted(all_nodes, key=lambda n: n["partner_gesamt"], reverse=True)[:18]
    out.append('<rect x="60" y="1300" width="2280" height="250" rx="14" fill="#fff" stroke="#dbe3ee"/>')
    out.append('<text x="80" y="1332" style="font-size:24px;font-weight:700;fill:#0f172a;">Top 18 Helios-Zentren nach Partnerzahl (ONKO/VISZ/URO)</text>')
    for i, n in enumerate(top):
        col, row = divmod(i, 6)
        x = 80 + col * 760
        y = 1370 + row * 28
        out.append(
            f'<text class="small" x="{x}" y="{y}">{i+1:02d}. {esc(n["name"])} '
            f'| Kategorie: {esc(n["domain"])} | Partner gesamt: {n["partner_gesamt"]} '
            f'| extern: {n["partner_extern"]} | Helios-intern: {n["partner_helios_intern"]}</text>'
        )

    out.append("</svg>")

    metrics = {
        "anzahl_onko_helios": len(onco_nodes),
        "anzahl_visz_helios": len(visz_nodes),
        "anzahl_uro_helios": len(uro_nodes),
        "partner_gesamt_ueber_alle_zentren": sum(n["partner_gesamt"] for n in all_nodes),
        "partner_extern_ueber_alle_zentren": sum(n["partner_extern"] for n in all_nodes),
        "helios_partner_ohne_helios_zentrum": len(helios_partner_ohne_zentrum),
    }
    return "\n".join(out), metrics


def main() -> None:
    args = parse_args()
    svg, metrics = build_map(args)
    out_path = Path(args.output)
    out_path.write_text(svg, encoding="utf-8")
    print(f"SVG gespeichert: {out_path}")
    for k, v in metrics.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
