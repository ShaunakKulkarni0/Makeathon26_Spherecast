Gute Frage — und da gibt es eine klare Antwort, die ich direkt an euren Daten festmachen kann.

## Das Problem mit reiner Synonym-Suche

Synonyme sind **nicht reliable genug** als einzige Methode, weil:

- `magnesium-stearate` und `magnesium` teilen das Wort "magnesium" — aber sind komplett verschiedene Dinge (Fließmittel vs. Nährstoff)
- `natural-flavor` und `natural-flavors` — identisch, aber unterschiedliche Slugs
- `vitamin-b6`, `pyridoxine-hcl`, `pyridoxine-hydrochloride-vitamin-b6`, `vitamin-b6-pyridoxal-5-phosphate` — teils identisch, teils **verschiedene Formen** mit verschiedener Bioverfügbarkeit

Reine String-Matching oder Thesaurus-Suche würde das nicht sauber trennen.

---

## Die beste skalierbare Lösung: Embedding-basiertes Clustering + LLM-Verifikation

Das ist ein klassisches **zweistufiges System:**

```
Stufe 1 — Embedding Similarity (schnell, skalierbar)
   → Clustert alle 876 Slugs nach semantischer Ähnlichkeit
   → Gibt dir Kandidaten-Gruppen

Stufe 2 — LLM-Verifikation (gezielt, pro Cluster)
   → Bewertet jeden Cluster: "Sind das wirklich dasselbe?"
   → Gibt Konfidenz + Begründung zurück
```

**Warum Embeddings zuerst?**
876 Slugs × 876 = ~380.000 Paare. Die alle per LLM zu prüfen wäre teuer und langsam. Embeddings reduzieren das auf ~50-100 interessante Cluster, die dann per LLM verifiziert werden.

---

## Konkret: Was ihr nutzen solltet

**Für Embeddings:** `text-embedding-3-small` von OpenAI oder direkt Claude — aber noch besser: eine **chemische/biomedizinische Ontologie** als Grundlage.

Das ist der eigentliche Geheimtipp:

### PubChem / UMLS / ChEBI als Ground Truth

```
vitamin c     → PubChem CID 54670067 → Synonyme: ascorbic acid, L-ascorbic acid, ...
ascorbic acid → PubChem CID 54670067 → selbe CID!
```

PubChem hat eine kostenlose API und liefert euch für jeden Begriff:
- Canonical Name
- Alle bekannten Synonyme
- CAS-Nummer (eindeutige chemische ID)
- Molecular Formula

Das ist **100% reliable** für chemische Substanzen — keine Halluzinationen, kein Rauschen.

---

## Empfohlene Architektur für euch

```
1. PubChem API  →  für jeden Slug die CAS-Nummer / CID holen
                   (deckt ~70% der Fälle zuverlässig ab)

2. Embeddings   →  für die restlichen Slugs ohne klaren PubChem-Match
                   (z.B. "natural-flavor", "b-vitamins", "digestive-enzymes")

3. LLM          →  finale Verifikation + Tier-Klassifikation
                   (exact / functional equivalent / same category)
```

### Was PubChem NICHT abdeckt:
- Generische Begriffe wie `natural-flavor`, `b-vitamins`, `digestive-enzymes`
- Proprietary Branded Ingredients wie `magtein`
- Funktionale Kategorien wie `magnesium` (welche Form?)

Genau da springt dann Stufe 2 (Embeddings) und Stufe 3 (LLM) ein.

---

## Fazit

| Methode | Reliabilität | Skalierbarkeit | Einsatzbereich |
|---|---|---|---|
| Reine Synonym-Suche | ❌ niedrig | ✅ hoch | Nicht empfohlen allein |
| PubChem CAS-Lookup | ✅✅ sehr hoch | ✅ hoch | Chemische Substanzen |
| Embeddings + Clustering | ✅ mittel | ✅✅ sehr hoch | Alle Slugs als Vorfilter |
| LLM-Verifikation | ✅✅ hoch | ❌ teuer | Nur pro Cluster |

**Startet mit PubChem** — das ist der schnellste Weg zu verlässlichen Synonym-Gruppen und ihr könnt es heute noch implementieren.