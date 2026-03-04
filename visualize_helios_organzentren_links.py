#!/usr/bin/env python3
"""Visualize Helios Organzentren linked to non-Helios oncological centers.

Outputs a self-contained SVG without third-party dependencies.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--centers", default="fulldb_centers.json", help="Path to centers JSON")
    parser.add_argument("--oncos", default="fulldb_oncos.json", help="Path to oncos JSON")
    parser.add_argument(
        "--onco-links",
        default="fulldb_oncos_centers.json",
        help="Path to onco-center relation JSON",
    )
    parser.add_argument(
        "--output",
        default="helios_organzentren_to_nonhelios_oncos.svg",
        help="Output SVG path",
    )
    return parser.parse_args()


def load_json(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def is_helios(record: dict) -> bool:
    haystack = " ".join(str(record.get(k, "")) for k in ("inst1", "inst2", "basement"))
    return "helios" in haystack.lower()


def label_center(center: dict) -> str:
    return f"{center.get('organ', 'NA')}: {center.get('inst1', 'Unknown')}"


def label_onco(onco: dict) -> str:
    return onco.get("inst1", f"Onko #{onco.get('id', 'NA')}")


def escape(text: str) -> str:
    return html.escape(text, quote=True)


def visualize(centers_path: str, oncos_path: str, links_path: str, output: str) -> None:
    centers = {row["id"]: row for row in load_json(centers_path)}
    oncos = {row["id"]: row for row in load_json(oncos_path)}
    links = load_json(links_path)

    filtered_pairs: list[tuple[dict, dict]] = []
    for link in links:
        center = centers.get(link.get("c_id"))
        onco = oncos.get(link.get("n_id"))
        if not center or not onco:
            continue
        if is_helios(center) and not is_helios(onco):
            filtered_pairs.append((center, onco))

    unique_centers = {}
    unique_oncos = {}
    edges = []
    for center, onco in filtered_pairs:
        clabel = label_center(center)
        olabel = label_onco(onco)
        unique_centers[clabel] = center
        unique_oncos[olabel] = onco
        edges.append((clabel, olabel))

    if not edges:
        raise SystemExit("No Helios Organzentren -> non-Helios Onkozentrum links found.")

    left_nodes = sorted(unique_centers.keys())
    right_nodes = sorted(unique_oncos.keys())

    width = 1800
    margin_top = 80
    margin_bottom = 60
    row_h = 80
    rows = max(len(left_nodes), len(right_nodes))
    height = margin_top + margin_bottom + row_h * max(rows, 1)

    left_x = 280
    right_x = width - 280

    left_y = {name: margin_top + row_h * i + row_h // 2 for i, name in enumerate(left_nodes)}
    right_y = {name: margin_top + row_h * i + row_h // 2 for i, name in enumerate(right_nodes)}

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">')
    svg.append('<style>text { font-family: Arial, sans-serif; } .title { font-size: 28px; font-weight: bold; } .hdr { font-size: 20px; font-weight: bold; } .label { font-size: 15px; } </style>')
    svg.append(f'<text class="title" x="{width // 2}" y="40" text-anchor="middle">Helios Organzentren tied to non-Helios Onkologische Zentren</text>')
    svg.append(f'<text class="hdr" x="{left_x}" y="70" text-anchor="middle">Helios Organzentren</text>')
    svg.append(f'<text class="hdr" x="{right_x}" y="70" text-anchor="middle">Non-Helios Onkozentren</text>')

    for l_name, r_name in edges:
        svg.append(
            f'<line x1="{left_x}" y1="{left_y[l_name]}" x2="{right_x}" y2="{right_y[r_name]}" stroke="#4a6ea9" stroke-width="2" opacity="0.6" />'
        )

    for name, y in left_y.items():
        svg.append(f'<circle cx="{left_x}" cy="{y}" r="8" fill="#2b8cbe" />')
        svg.append(f'<text class="label" x="{left_x - 14}" y="{y + 5}" text-anchor="end">{escape(name)}</text>')

    for name, y in right_y.items():
        svg.append(f'<circle cx="{right_x}" cy="{y}" r="8" fill="#e34a33" />')
        svg.append(f'<text class="label" x="{right_x + 14}" y="{y + 5}" text-anchor="start">{escape(name)}</text>')

    svg.append("</svg>")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(svg), encoding="utf-8")

    print(f"Saved visualization to: {output_path}")
    print(f"Edges: {len(edges)}")
    print(f"Unique Helios Organzentren: {len(left_nodes)}")
    print(f"Unique non-Helios Onkozentren: {len(right_nodes)}")


if __name__ == "__main__":
    args = parse_args()
    visualize(args.centers, args.oncos, args.onco_links, args.output)
