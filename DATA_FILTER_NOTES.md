# OZ-Zuordnung ohne Annahmen (rein API-ID-basiert)

## Problem
Einige Organzentrum-Standorte stehen als `Ohne OZ-Zuordnung`, obwohl andere Standorte desselben Zentrums in `*_centers` bereits einer OZ-ID (`n_id`) zugeordnet sind.

## Datenmodell (aus den API-Exports)
- `fulldb_centers.json`: Organzentrum-Standorte (`id`, `organ`, `reg_nr`, ...)
- `fulldb_oncos_centers.json`: explizite OZ↔Zentrum-Zuordnung (`n_id`, `c_id`)
- `fulldb_viszes_centers.json`: explizite Viszeral↔Zentrum-Zuordnung (`n_id`, `c_id`)
- `fulldb_uros_centers.json`: explizite Uro↔Zentrum-Zuordnung (`n_id`, `c_id`)

## Robuste Logik
1. **Direkte Zuordnung** über `c_id` in `*_centers`.
2. **Standort-Bündelung über Zertifikats-ID**: `reg_nr` wird nur dann auf eine gemeinsame Gruppen-ID reduziert, wenn ein echter Standort-Suffix vorliegt (`...-<hauptid>-<standortnr>`).
   - Beispiel: `FAL-Z-019-1` → `FAL-Z-019`
   - Beispiel: `FAN-Z-152` bleibt `FAN-Z-152`
3. **Propagation innerhalb derselben Gruppen-ID + Organ**:
   - Wenn in einer Gruppe mindestens ein Standort eine direkte `n_id`-Zuordnung hat,
   - erhalten alle Standorte derselben Gruppe dieselbe(n) `n_id`-Zuordnung(en).

Wichtig: Kein Text-Matching von Namen/Ort, keine Heuristik über Kliniknamen.

## Umsetzung
Siehe `oz_assignment.py`.

## Verifikation der genannten Beispiele
- `Hämatoonkologisches Zentrum am Helios Klinikum Emil von Behring` (`FAN-Z-152`) bleibt unzugeordnet, solange in den API-Linktabellen keine passende `c_id`/Gruppen-Zuordnung existiert.
- `Lungenkrebszentrum Helios/Johanniter/Universitätsklinikum Bonn – Helios Siegburg` (`FAL-Z-019-1..4`) wird korrekt zugeordnet, da innerhalb derselben `reg_nr`-Gruppe direkte OZ-IDs vorliegen.
