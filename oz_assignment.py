#!/usr/bin/env python3
"""Build ID-based OZ assignment for organ centers.

Data sources (API exports):
- fulldb_centers.json
- fulldb_oncos.json + fulldb_oncos_centers.json
- fulldb_viszes.json + fulldb_viszes_centers.json
- fulldb_uros.json + fulldb_uros_centers.json

The assignment logic intentionally avoids fuzzy matching and uses only API IDs.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

CenterId = int
NetworkId = int
NetworkType = str
NetworkRef = Tuple[NetworkType, NetworkId]


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def center_group_id(reg_nr: str) -> str:
    """Normalize site-level reg numbers to a shared group id.

    Example:
    - FAL-Z-019-1 -> FAL-Z-019
    - FAL-Z-019-4 -> FAL-Z-019
    - FAN-Z-152   -> FAN-Z-152 (no site split)
    """
    if not reg_nr:
        return ""
    match = re.match(r"^(.*-\d+)-\d+$", reg_nr)
    return match.group(1) if match else reg_nr


def build_assignments(repo_root: Path) -> List[Dict]:
    centers = load_json(repo_root / "fulldb_centers.json")

    networks = {
        "OZ": {
            "meta": {n["id"]: n for n in load_json(repo_root / "fulldb_oncos.json")},
            "links": load_json(repo_root / "fulldb_oncos_centers.json"),
        },
        "Viszeral": {
            "meta": {n["id"]: n for n in load_json(repo_root / "fulldb_viszes.json")},
            "links": load_json(repo_root / "fulldb_viszes_centers.json"),
        },
        "Uro": {
            "meta": {n["id"]: n for n in load_json(repo_root / "fulldb_uros.json")},
            "links": load_json(repo_root / "fulldb_uros_centers.json"),
        },
    }

    direct_map: Dict[CenterId, Set[NetworkRef]] = defaultdict(set)
    for n_type, payload in networks.items():
        for rel in payload["links"]:
            direct_map[rel["c_id"]].add((n_type, rel["n_id"]))

    by_group: Dict[Tuple[str, str], List[CenterId]] = defaultdict(list)
    for center in centers:
        group_key = (center["organ"], center_group_id(center.get("reg_nr", "")))
        by_group[group_key].append(center["id"])

    final_map: Dict[CenterId, Set[NetworkRef]] = {
        center["id"]: set(direct_map.get(center["id"], set())) for center in centers
    }

    # Propagate only within explicit reg_nr groups to avoid text-based assumptions.
    for _, center_ids in by_group.items():
        grouped_refs: Set[NetworkRef] = set()
        for center_id in center_ids:
            grouped_refs |= final_map[center_id]
        if grouped_refs:
            for center_id in center_ids:
                final_map[center_id] |= grouped_refs

    enriched: List[Dict] = []
    for center in centers:
        refs = sorted(final_map[center["id"]], key=lambda item: (item[0], item[1]))
        resolved = [
            {
                "network_type": n_type,
                "network_id": n_id,
                "network_name": networks[n_type]["meta"].get(n_id, {}).get("inst1", ""),
                "network_location": networks[n_type]["meta"].get(n_id, {}).get("loc", ""),
            }
            for n_type, n_id in refs
        ]

        enriched.append(
            {
                "center_id": center["id"],
                "organ": center.get("organ", ""),
                "inst1": center.get("inst1", ""),
                "inst2": center.get("inst2", ""),
                "reg_nr": center.get("reg_nr", ""),
                "group_reg_nr": center_group_id(center.get("reg_nr", "")),
                "direct_network_refs": [
                    {"network_type": n_type, "network_id": n_id}
                    for n_type, n_id in sorted(direct_map.get(center["id"], set()))
                ],
                "resolved_network_refs": resolved,
                "is_unassigned": len(resolved) == 0,
            }
        )

    return enriched


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate robust OZ assignment map from API IDs")
    parser.add_argument(
        "--output",
        default="oz_assignment_enriched.json",
        help="Output JSON path (default: oz_assignment_enriched.json)",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent
    enriched = build_assignments(repo_root)

    output_path = repo_root / args.output
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(enriched)} records to {output_path}")


if __name__ == "__main__":
    main()
