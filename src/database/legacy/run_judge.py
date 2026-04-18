import sqlite3
from pathlib import Path
from matcher import judge_pair

def parse_similarity_groups(filepath: str) -> list[dict]:
    """Parst die Datei und entfernt direkte A->B / B->A Duplikate."""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    pairs = []
    processed_pairs = set()
    current_base = None

    for line in lines:
        cleaned = line.strip()
        
        # Ignoriere Trennlinien und leere Zeilen
        if not cleaned or cleaned.startswith("==") or cleaned.startswith("GRUPPE"):
            continue

        # Finde die Base-SKU (startet mit ●)
        if cleaned.startswith("●"):
            current_base = cleaned.replace("●", "").strip()
            
        # Finde die Target-SKUs (starten mit einer Zahl wie 1.0000)
        elif current_base and cleaned[0].isdigit():
            parts = cleaned.split()
            if len(parts) >= 2:
                score = float(parts[0])
                target = parts[1]

                if current_base == target:
                    continue

                # Sortieren, damit (A,B) und (B,A) als das exakt gleiche Paar erkannt werden
                pair_tuple = tuple(sorted([current_base, target]))
                
                if pair_tuple not in processed_pairs:
                    processed_pairs.add(pair_tuple)
                    pairs.append({
                        "sku_a": pair_tuple[0],
                        "sku_b": pair_tuple[1],
                        "score": score
                    })
    return pairs


if __name__ == "__main__":
    # ---------------------------------------------------------
    # PFADE ANPASSEN (relativ zum Ort, von dem du das Skript startest)
    # ---------------------------------------------------------
    DB_PATH = "../../db.sqlite" 
    TEXT_FILE_PATH = "../../similarity_groups.txt"
    OUTPUT_FILE = "../../new_groups.txt"

    print("\n🚀 Lese similarity_groups.txt ein...")
    pairs_to_judge = parse_similarity_groups(TEXT_FILE_PATH)
    print(f"✅ {len(pairs_to_judge)} einzigartige Vektor-Paare gefunden.\n")

    try:
        conn = sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"❌ Fehler: Konnte keine Verbindung zur DB aufbauen: {e}")
        exit(1)

    print("🧠 Starte LLM Matching Judge...\n" + "-"*50)

    # --- CLUSTERING LOGIK ---
    sku_to_group = {}   # Speichert, in welcher Gruppe eine SKU bereits ist (z.B. SKU_A -> "Vitamin C")
    final_groups = {}   # Speichert die finalen Gruppen (z.B. "Vitamin C" -> {SKU_A, SKU_B})

    # HINWEIS FÜR DEN HACKATHON:
    # Entferne das [:50], um das ganze Skript über alle Daten laufen zu lassen!
    # Für den Testlauf lassen wir es nur über die ersten 50 Paare laufen.
    for pair in pairs_to_judge[:50]:
        sku_a = pair["sku_a"]
        sku_b = pair["sku_b"]

        # -------------------------------------------------------------
        # SMART SKIP: Wenn beide schon in derselben Gruppe sind, überspringe den LLM-Call!
        # -------------------------------------------------------------
        if sku_a in sku_to_group and sku_b in sku_to_group and sku_to_group[sku_a] == sku_to_group[sku_b]:
            print(f"⏭️  SKIP: {sku_a} & {sku_b} sind bereits in Gruppe '{sku_to_group[sku_a]}'")
            continue

        try:
            # Sende an LLM
            result = judge_pair(
                conn=conn,
                sku_id_a=sku_a,
                sku_id_b=sku_b,
                cosine_similarity=pair["score"]
            )
            
            # --- CLEAN TERMINAL OUTPUT ---
            if result.belongs_to_same_group:
                print(f"✅ MATCH  | {result.group_title}")
                print(f"   ├─ {sku_a}")
                print(f"   ├─ {sku_b}")
                print(f"   └─ Reason: {result.reasoning}\n")
                
                title = result.group_title
                
                # In unserem Dictionary speichern
                if title not in final_groups:
                    final_groups[title] = set()
                
                final_groups[title].update([sku_a, sku_b])
                sku_to_group[sku_a] = title
                sku_to_group[sku_b] = title
                
            else:
                print(f"❌ REJECT | {sku_a} =/= {sku_b}")
                print(f"   └─ Reason: {result.reasoning}\n")

        except Exception as e:
            print(f"⚠️  ERROR bei Paar {sku_a} <-> {sku_b}: {e}")

    conn.close()

    # ---------------------------------------------------------
    # SCHREIBE DAS FINALE CLUSTERING IN DIE TEXTDATEI
    # ---------------------------------------------------------
    print("\n" + "="*50)
    print(f"💾 Speichere saubere Gruppen in {OUTPUT_FILE}...")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("=== AGNES AI: CONSOLIDATED SOURCING GROUPS ===\n")
        f.write("Generiert durch Vector Search + LLM Verification\n\n")
        
        # Sortiere die Gruppen alphabetisch
        for title in sorted(final_groups.keys()):
            skus = sorted(list(final_groups[title]))
            
            f.write(f"📦 GROUP: {title} ({len(skus)} SKUs)\n")
            f.write("═" * 60 + "\n")
            for sku in skus:
                f.write(f"  ● {sku}\n")
            f.write("\n")

    print("✅ Fertig! Schau dir deine new_groups.txt an!")