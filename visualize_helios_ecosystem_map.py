#!/usr/bin/env python3
"""Erstellt eine interaktive HTML-Karte für Helios ONKO/VISZ/URO-Zentren.

Interaktiv:
- Klick auf ein Helios-Zentrum zeigt zugeordnete Partner.
- Farbcode Partner: intern (Helios) vs. extern.
- Filter für Kategorien (ONKO/VISZ/URO) und Partner-Typen.
"""

from __future__ import annotations

import argparse
import html
import json
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
    p.add_argument("--output", default="helios_ecosystem_interaktiv.html")
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


def short_name(value: str, max_len: int = 70) -> str:
    if len(value) <= max_len:
        return value
    return value[: max_len - 3] + "..."


def build_domain_items(domain_name: str, raw_nodes: list[dict], node_links: list[dict], center_to_partners: dict[int, set[int]], partners: dict[int, dict]) -> list[dict]:
    helios_nodes = [n for n in raw_nodes if is_helios(n)]
    valid_ids = {n["id"] for n in helios_nodes}

    node_to_centers: dict[int, set[int]] = defaultdict(set)
    for rel in node_links:
        nid = rel.get("n_id")
        cid = rel.get("c_id")
        if isinstance(nid, int) and isinstance(cid, int) and nid in valid_ids:
            node_to_centers[nid].add(cid)

    items = []
    for n in helios_nodes:
        nid = n["id"]
        center_ids = node_to_centers.get(nid, set())
        pids: set[int] = set()
        for cid in center_ids:
            pids.update(center_to_partners.get(cid, set()))

        partner_items = []
        for pid in sorted(pids):
            p = partners.get(pid)
            if not p:
                continue
            partner_items.append(
                {
                    "id": pid,
                    "name": short_name(p.get("inst1") or p.get("inst2") or f"Partner {pid}"),
                    "ort": p.get("loc", ""),
                    "typ": "intern" if is_helios(p) else "extern",
                }
            )

        partner_items.sort(key=lambda x: (x["typ"], x["name"]))
        items.append(
            {
                "id": nid,
                "domain": domain_name,
                "name": short_name(n.get("inst1") or n.get("inst2") or f"Zentrum {nid}"),
                "ort": n.get("loc", ""),
                "center_count": len(center_ids),
                "partners": partner_items,
                "partner_gesamt": len(partner_items),
                "partner_intern": sum(1 for x in partner_items if x["typ"] == "intern"),
                "partner_extern": sum(1 for x in partner_items if x["typ"] == "extern"),
            }
        )

    return sorted(items, key=lambda x: x["partner_gesamt"], reverse=True)


def build_html(args: argparse.Namespace) -> tuple[str, dict]:
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
    linked_to_helios = {
        rel["p_id"]
        for rel in partner_links
        if isinstance(rel.get("p_id"), int)
        and isinstance(rel.get("c_id"), int)
        and rel["c_id"] in helios_center_ids
    }
    helios_partner_ohne_zentrum = len(helios_partner_ids - linked_to_helios)

    onko = build_domain_items(
        "ONKO", load_json(args.oncos), load_json(args.onco_links), center_to_partners, partners
    )
    visz = build_domain_items(
        "VISZ", load_json(args.viszes), load_json(args.visz_links), center_to_partners, partners
    )
    uro = build_domain_items(
        "URO", load_json(args.uros), load_json(args.uro_links), center_to_partners, partners
    )

    data = {"ONKO": onko, "VISZ": visz, "URO": uro}
    all_centers = onko + visz + uro

    metrics = {
        "anzahl_onko": len(onko),
        "anzahl_visz": len(visz),
        "anzahl_uro": len(uro),
        "helios_partner_ohne_zentrum": helios_partner_ohne_zentrum,
        "zentren_gesamt": len(all_centers),
    }

    payload = html.escape(json.dumps(data, ensure_ascii=False))

    page = f"""<!doctype html>
<html lang=\"de\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\" />
  <title>Interaktive Helios-Karte (ONKO/VISZ/URO)</title>
  <style>
    body {{ font-family: Inter, Segoe UI, Arial, sans-serif; margin: 0; background:#f8fafc; color:#0f172a; }}
    .wrap {{ display:grid; grid-template-columns: 420px 1fr; gap:14px; height:100vh; padding:14px; box-sizing:border-box; }}
    .card {{ background:white; border:1px solid #dbe3ee; border-radius:14px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }}
    .left {{ display:flex; flex-direction:column; min-height:0; }}
    .pad {{ padding:14px 16px; }}
    .title {{ font-size:22px; font-weight:700; margin:0 0 4px 0; }}
    .sub {{ font-size:13px; color:#475569; margin:0; }}
    .kpi {{ display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:10px; }}
    .kpi .box {{ border:1px solid #e2e8f0; border-radius:10px; padding:8px 10px; }}
    .kpi .l {{ font-size:12px; color:#64748b; }}
    .kpi .v {{ font-size:20px; font-weight:700; }}
    .controls {{ display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:10px; }}
    .controls label {{ font-size:13px; background:#f1f5f9; border-radius:999px; padding:6px 10px; }}
    .search {{ width:100%; margin-top:10px; padding:8px 10px; border:1px solid #cbd5e1; border-radius:10px; box-sizing:border-box; }}
    #centerList {{ overflow:auto; min-height:0; border-top:1px solid #e2e8f0; }}
    .center-item {{ padding:10px 14px; border-bottom:1px solid #f1f5f9; cursor:pointer; }}
    .center-item:hover {{ background:#f8fafc; }}
    .center-item.active {{ background:#eef2ff; border-left:4px solid #4f46e5; padding-left:10px; }}
    .tag {{ display:inline-block; font-size:11px; border-radius:999px; padding:2px 8px; margin-right:6px; color:white; }}
    .ONKO{{background:#8e44ad;}} .VISZ{{background:#16a085;}} .URO{{background:#e67e22;}}
    .meta {{ font-size:12px; color:#475569; margin-top:4px; }}
    .main {{ position:relative; overflow:auto; }}
    .legend {{ position:absolute; top:14px; right:14px; background:white; border:1px solid #dbe3ee; border-radius:12px; padding:10px 12px; font-size:12px; }}
    svg {{ width:100%; height:100%; min-height:850px; display:block; }}
    .hint {{ position:absolute; left:16px; top:14px; background:#0f172a; color:white; padding:7px 10px; border-radius:10px; font-size:12px; opacity:.9; }}
  </style>
</head>
<body>
<div class=\"wrap\">
  <section class=\"card left\">
    <div class=\"pad\">
      <h1 class=\"title\">Interaktive Helios-Karte</h1>
      <p class=\"sub\">Klick auf ein Zentrum: rechts siehst du alle zugeordneten Partner (intern/extern farbig).</p>
      <div class=\"kpi\">
        <div class=\"box\"><div class=\"l\">ONKO-Zentren</div><div class=\"v\">{metrics['anzahl_onko']}</div></div>
        <div class=\"box\"><div class=\"l\">VISZ-Zentren</div><div class=\"v\">{metrics['anzahl_visz']}</div></div>
        <div class=\"box\"><div class=\"l\">URO-Zentren</div><div class=\"v\">{metrics['anzahl_uro']}</div></div>
        <div class=\"box\"><div class=\"l\">Helios-Partner ohne Helios-Zentrum</div><div class=\"v\">{metrics['helios_partner_ohne_zentrum']}</div></div>
      </div>
      <div class=\"controls\">
        <label><input type=\"checkbox\" id=\"fONKO\" checked> ONKO</label>
        <label><input type=\"checkbox\" id=\"fVISZ\" checked> VISZ</label>
        <label><input type=\"checkbox\" id=\"fURO\" checked> URO</label>
        <label><input type=\"checkbox\" id=\"fIntern\" checked> nur intern</label>
        <label><input type=\"checkbox\" id=\"fExtern\" checked> nur extern</label>
      </div>
      <input id=\"search\" class=\"search\" placeholder=\"Zentrum suchen...\" />
    </div>
    <div id=\"centerList\"></div>
  </section>

  <section class=\"card main\">
    <div class=\"hint\">Interaktiv: Zoomen per Browser, Partner über Tooltip lesen.</div>
    <div class=\"legend\">
      <div><span style=\"display:inline-block;width:10px;height:10px;border-radius:50%;background:#334155\"></span> Zentrum</div>
      <div><span style=\"display:inline-block;width:10px;height:10px;border-radius:50%;background:#2563eb\"></span> Partner intern (Helios)</div>
      <div><span style=\"display:inline-block;width:10px;height:10px;border-radius:50%;background:#dc2626\"></span> Partner extern</div>
      <div style=\"margin-top:4px;color:#475569\">Linien = Zuordnung Zentrum → Partner</div>
    </div>
    <svg id=\"viz\" viewBox=\"0 0 1600 960\" preserveAspectRatio=\"xMidYMid meet\"></svg>
  </section>
</div>

<script id=\"dataset\" type=\"application/json\">{payload}</script>
<script>
const data = JSON.parse(document.getElementById('dataset').textContent);
const colors = {{ ONKO:'#8e44ad', VISZ:'#16a085', URO:'#e67e22' }};
const listEl = document.getElementById('centerList');
const svg = document.getElementById('viz');
const searchEl = document.getElementById('search');
let selected = null;

function allCenters() {{
  return [...data.ONKO, ...data.VISZ, ...data.URO];
}}

function currentFilter() {{
  return {{
    ONKO: document.getElementById('fONKO').checked,
    VISZ: document.getElementById('fVISZ').checked,
    URO: document.getElementById('fURO').checked,
    intern: document.getElementById('fIntern').checked,
    extern: document.getElementById('fExtern').checked,
    q: searchEl.value.trim().toLowerCase()
  }};
}}

function filteredCenters() {{
  const f = currentFilter();
  return allCenters().filter(c => f[c.domain] && (!f.q || c.name.toLowerCase().includes(f.q)));
}}

function renderList() {{
  const f = currentFilter();
  const arr = filteredCenters();
  listEl.innerHTML = '';
  arr.forEach(c => {{
    const row = document.createElement('div');
    row.className = 'center-item' + (selected && selected.id === c.id && selected.domain === c.domain ? ' active' : '');
    row.innerHTML = `<div><span class="tag ${{c.domain}}">${{c.domain}}</span>${{c.name}}</div>
      <div class="meta">Ort: ${{c.ort || '-'}} · Partner gesamt: ${{c.partner_gesamt}} · intern: ${{c.partner_intern}} · extern: ${{c.partner_extern}}</div>`;
    row.onclick = () => {{ selected = c; renderList(); renderGraph(); }};
    listEl.appendChild(row);
  }});

  if ((!selected || !arr.find(x => x.id === selected.id && x.domain === selected.domain)) && arr.length) {{
    selected = arr[0];
    renderList();
    renderGraph();
  }} else if (!arr.length) {{
    selected = null;
    renderGraph();
  }}
}}

function drawCircle(cx, cy, r, fill, stroke, sw, title='') {{
  const c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
  c.setAttribute('cx', cx); c.setAttribute('cy', cy); c.setAttribute('r', r);
  c.setAttribute('fill', fill); c.setAttribute('stroke', stroke); c.setAttribute('stroke-width', sw);
  if (title) {{
    const t = document.createElementNS('http://www.w3.org/2000/svg', 'title');
    t.textContent = title; c.appendChild(t);
  }}
  svg.appendChild(c);
  return c;
}}

function drawText(x,y,text,size=13,color='#0f172a',anchor='start',weight='400') {{
  const t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  t.setAttribute('x',x); t.setAttribute('y',y); t.setAttribute('font-size',size);
  t.setAttribute('fill',color); t.setAttribute('text-anchor',anchor); t.setAttribute('font-weight',weight);
  t.textContent = text; svg.appendChild(t); return t;
}}

function drawLine(x1,y1,x2,y2,color='#94a3b8',w=1.4) {{
  const l = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  l.setAttribute('x1',x1); l.setAttribute('y1',y1); l.setAttribute('x2',x2); l.setAttribute('y2',y2);
  l.setAttribute('stroke',color); l.setAttribute('stroke-width',w); l.setAttribute('opacity','0.75');
  svg.appendChild(l); return l;
}}

function renderGraph() {{
  svg.innerHTML = '';
  drawText(40,52,'Zentrum-Partner-Zuordnung',28,'#0f172a','start','700');

  if (!selected) {{
    drawText(40,95,'Keine Zentren für den aktuellen Filter gefunden.',16,'#64748b');
    return;
  }}

  const f = currentFilter();
  const partners = selected.partners.filter(p => (p.typ === 'intern' ? f.intern : f.extern));
  const cx = 280, cy = 490;

  drawCircle(cx, cy, 44, '#334155', '#0f172a', 2.2,
    `${{selected.name}}\nKategorie: ${{selected.domain}}\nPartner gesamt: ${{selected.partner_gesamt}}`);
  drawText(cx, cy + 6, selected.domain, 16, '#fff', 'middle', '700');
  drawText(40,112, selected.name, 18, colors[selected.domain], 'start', '700');
  drawText(40,140, `Ort: ${{selected.ort || '-'}} · angebundene Organzentren: ${{selected.center_count}}`, 14, '#475569');
  drawText(40,164, `Partner (gefiltert): ${{partners.length}} · intern: ${{partners.filter(p => p.typ==='intern').length}} · extern: ${{partners.filter(p => p.typ==='extern').length}}`, 14, '#475569');

  const cols = 4;
  const startX = 610;
  const startY = 190;
  const rowH = 92;
  const colW = 230;

  partners.forEach((p, i) => {{
    const col = Math.floor(i / 9) % cols;
    const row = i % 9;
    const block = Math.floor(i / (9 * cols));
    const x = startX + col * colW + block * (cols * colW + 30);
    const y = startY + row * rowH;

    drawLine(cx + 44, cy, x - 18, y, p.typ === 'intern' ? '#60a5fa' : '#f87171', 1.2);
    drawCircle(x, y, 11, p.typ === 'intern' ? '#2563eb' : '#dc2626', '#111827', 1.0,
      `${{p.name}}\nTyp: ${{p.typ}}\nOrt: ${{p.ort || '-'}}`);
    drawText(x + 16, y + 4, p.name, 12, '#0f172a');
    drawText(x + 16, y + 20, p.typ === 'intern' ? 'intern (Helios)' : 'extern', 11, p.typ === 'intern' ? '#1d4ed8' : '#b91c1c');
  }});

  if (!partners.length) {{
    drawText(610, 210, 'Für diesen Filter sind keine Partner sichtbar.', 15, '#64748b');
  }}
}}

['fONKO','fVISZ','fURO','fIntern','fExtern'].forEach(id => document.getElementById(id).addEventListener('change', () => {{ renderList(); }}));
searchEl.addEventListener('input', () => renderList());

renderList();
</script>
</body>
</html>
"""
    return page, metrics


def main() -> None:
    args = parse_args()
    html_doc, metrics = build_html(args)
    out = Path(args.output)
    out.write_text(html_doc, encoding="utf-8")
    print(f"Datei geschrieben: {out}")
    for k, v in metrics.items():
        print(f"{k}: {v}")


if __name__ == "__main__":
    main()
