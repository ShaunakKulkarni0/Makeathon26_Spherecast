# src/database/shared/check_similarity.py
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "src/database/layers"))
sys.path.insert(0, str(ROOT / "src/database/shared"))

from embedder import load_all_embeddings
from matcher import _cosine_similarity

conn = sqlite3.connect(ROOT / "db.sqlite")
names = dict(conn.execute("SELECT Id, SKU FROM Product").fetchall())
all_emb = load_all_embeddings(conn)
embedding_map = {sid: vec for sid, vec in all_emb}
conn.close()

print(f"Embeddings geladen: {len(embedding_map)} SKUs\n")

CLUSTER_THRESHOLD = 0.9  # Nur wirklich ähnliche SKUs in einer Gruppe
SHOW_THRESHOLD    = 0.9  # Nur Matches über diesem Wert im Output zeigen

# ---------------------------------------------------------------------------
# Union-Find Clustering (nur bei CLUSTER_THRESHOLD)
# ---------------------------------------------------------------------------
parent = {sid: sid for sid in embedding_map}

def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x

def union(x, y):
    parent[find(x)] = find(y)

ids = list(embedding_map.keys())

# Alle Paare einmal berechnen und cachen
print("Berechne Similarities...")
pair_scores: dict[tuple[int,int], float] = {}
for i, id_a in enumerate(ids):
    for id_b in ids[i+1:]:
        sim = _cosine_similarity(embedding_map[id_a], embedding_map[id_b])
        pair_scores[(id_a, id_b)] = sim
        if sim >= CLUSTER_THRESHOLD:
            union(id_a, id_b)

# Gruppen zusammenbauen
clusters: dict[int, list[int]] = {}
for sid in embedding_map:
    root = find(sid)
    clusters.setdefault(root, []).append(sid)

# Nur Gruppen mit mehr als einem SKU
multi = sorted(
    [m for m in clusters.values() if len(m) > 1],
    key=len, reverse=True
)

total_llm_calls = sum(len(m) * (len(m) - 1) // 2 for m in multi)
print(f"=== {len(multi)} Gruppen gefunden (Cluster-Threshold: {CLUSTER_THRESHOLD}) ===")
print(f"=== ~{total_llm_calls} LLM Judge Calls ===\n")

# ---------------------------------------------------------------------------
# Output — nur Matches über SHOW_THRESHOLD
# ---------------------------------------------------------------------------
output_lines = []

for i, members in enumerate(multi, 1):
    # Repräsentativer Name = kürzester SKU-Name in der Gruppe
    group_label = min((names.get(sid, str(sid)) for sid in members), key=len)
    
    output_lines.append(f"{'═'*60}")
    output_lines.append(f"  GRUPPE {i} ({len(members)} SKUs) — {group_label}")
    output_lines.append(f"{'═'*60}")

    for id_a in members:
        matches = []
        for id_b in members:
            if id_a == id_b:
                continue
            key = (min(id_a,id_b), max(id_a,id_b))
            sim = pair_scores[key]
            if sim >= SHOW_THRESHOLD:
                matches.append((sim, id_b))
        matches.sort(reverse=True)

        output_lines.append(f"  ● {names.get(id_a, str(id_a))}")
        for sim, match_id in matches:
            output_lines.append(f"      {sim:.4f}  {names.get(match_id, str(match_id))}")
    
    output_lines.append("")

full_output = "\n".join(output_lines)
print(full_output)

out_path = ROOT / "similarity_groups.txt"
out_path.write_text(full_output, encoding="utf-8")
print(f"\n→ Gespeichert in: {out_path}")