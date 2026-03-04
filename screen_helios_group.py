#!/usr/bin/env python3
"""Screen all database JSON files for records related to the Helios Group.

The script finds direct text matches and then expands through link tables to
capture related entities (centers, partners, and certified networks).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}, got {type(data).__name__}")
    return data


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).lower()


def row_matches(row: dict[str, Any], terms: list[str]) -> bool:
    haystack = " ".join(normalize(value) for value in row.values())
    return any(term in haystack for term in terms)


def by_id(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows if key in row}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=".",
        type=Path,
        help="Directory containing fulldb_*.json files (default: current directory)",
    )
    parser.add_argument(
        "--search",
        default="Helios Group",
        help="Search phrase used for direct text matching (default: 'Helios Group')",
    )
    parser.add_argument(
        "--output",
        default=Path("helios_screening_report.json"),
        type=Path,
        help="Path for JSON report output",
    )
    args = parser.parse_args()

    search_terms = sorted(
        {
            token.strip().lower()
            for token in [args.search, "helios", "helios group"]
            if token.strip()
        }
    )

    data_dir = args.data_dir
    centers = load_json(data_dir / "fulldb_centers.json")
    partners = load_json(data_dir / "fulldb_partners.json")
    oncos = load_json(data_dir / "fulldb_oncos.json")
    uros = load_json(data_dir / "fulldb_uros.json")
    viszes = load_json(data_dir / "fulldb_viszes.json")

    oncos_centers = load_json(data_dir / "fulldb_oncos_centers.json")
    uros_centers = load_json(data_dir / "fulldb_uros_centers.json")
    viszes_centers = load_json(data_dir / "fulldb_viszes_centers.json")
    partners_centers = load_json(data_dir / "fulldb_partners_centers.json")

    direct_centers = [row for row in centers if row_matches(row, search_terms)]
    direct_partners = [row for row in partners if row_matches(row, search_terms)]
    direct_oncos = [row for row in oncos if row_matches(row, search_terms)]
    direct_uros = [row for row in uros if row_matches(row, search_terms)]
    direct_viszes = [row for row in viszes if row_matches(row, search_terms)]

    center_ids = {str(row["id"]) for row in direct_centers if "id" in row}
    partner_ids = {str(row["id"]) for row in direct_partners if "id" in row}
    onco_ids = {str(row["id"]) for row in direct_oncos if "id" in row}
    uro_ids = {str(row["id"]) for row in direct_uros if "id" in row}
    visz_id_set = {str(row["id"]) for row in direct_viszes if "id" in row}

    related_partners_centers = [
        row
        for row in partners_centers
        if str(row.get("c_id", "")) in center_ids or str(row.get("p_id", "")) in partner_ids
    ]
    related_oncos_centers = [
        row
        for row in oncos_centers
        if str(row.get("c_id", "")) in center_ids or str(row.get("n_id", "")) in onco_ids
    ]
    related_uros_centers = [
        row
        for row in uros_centers
        if str(row.get("c_id", "")) in center_ids or str(row.get("n_id", "")) in uro_ids
    ]
    related_viszes_centers = [
        row
        for row in viszes_centers
        if str(row.get("c_id", "")) in center_ids or str(row.get("n_id", "")) in visz_id_set
    ]

    center_ids.update(str(row.get("c_id", "")) for row in related_partners_centers if row.get("c_id") is not None)
    center_ids.update(str(row.get("c_id", "")) for row in related_oncos_centers if row.get("c_id") is not None)
    center_ids.update(str(row.get("c_id", "")) for row in related_uros_centers if row.get("c_id") is not None)
    center_ids.update(str(row.get("c_id", "")) for row in related_viszes_centers if row.get("c_id") is not None)

    partner_ids.update(str(row.get("p_id", "")) for row in related_partners_centers if row.get("p_id") is not None)
    onco_ids.update(str(row.get("n_id", "")) for row in related_oncos_centers if row.get("n_id") is not None)
    uro_ids.update(str(row.get("n_id", "")) for row in related_uros_centers if row.get("n_id") is not None)
    visz_id_set.update(str(row.get("n_id", "")) for row in related_viszes_centers if row.get("n_id") is not None)

    centers_by_id = by_id(centers, "id")
    partners_by_id = by_id(partners, "id")
    oncos_by_id = by_id(oncos, "id")
    uros_by_id = by_id(uros, "id")
    viszes_by_id = by_id(viszes, "id")

    related_centers = [centers_by_id[cid] for cid in sorted(center_ids) if cid in centers_by_id]
    related_partners = [partners_by_id[pid] for pid in sorted(partner_ids) if pid in partners_by_id]
    related_oncos = [oncos_by_id[nid] for nid in sorted(onco_ids) if nid in oncos_by_id]
    related_uros = [uros_by_id[nid] for nid in sorted(uro_ids) if nid in uros_by_id]
    related_viszes = [viszes_by_id[nid] for nid in sorted(visz_id_set) if nid in viszes_by_id]

    report = {
        "search": args.search,
        "terms_used": search_terms,
        "counts": {
            "direct_centers": len(direct_centers),
            "direct_partners": len(direct_partners),
            "direct_oncos": len(direct_oncos),
            "direct_uros": len(direct_uros),
            "direct_viszes": len(direct_viszes),
            "related_centers": len(related_centers),
            "related_partners": len(related_partners),
            "related_oncos": len(related_oncos),
            "related_uros": len(related_uros),
            "related_viszes": len(related_viszes),
            "related_partners_centers_links": len(related_partners_centers),
            "related_oncos_centers_links": len(related_oncos_centers),
            "related_uros_centers_links": len(related_uros_centers),
            "related_viszes_centers_links": len(related_viszes_centers),
        },
        "direct_matches": {
            "centers": direct_centers,
            "partners": direct_partners,
            "oncos": direct_oncos,
            "uros": direct_uros,
            "viszes": direct_viszes,
        },
        "related_records": {
            "centers": related_centers,
            "partners": related_partners,
            "oncos": related_oncos,
            "uros": related_uros,
            "viszes": related_viszes,
            "partners_centers": related_partners_centers,
            "oncos_centers": related_oncos_centers,
            "uros_centers": related_uros_centers,
            "viszes_centers": related_viszes_centers,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    print(f"Wrote screening report to {args.output}")
    print(json.dumps(report["counts"], indent=2))


if __name__ == "__main__":
    main()
