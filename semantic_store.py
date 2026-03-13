"""
semantic_store.py
-----------------
Semantic memory layer for RosterIQ using FAISS.

Loads domain_knowledge.json, chunks it into individual entries,
embeds each chunk using sentence-transformers, and builds a FAISS
flat index for fast similarity search.

On every query, the agent embeds the incoming query and retrieves
the top-K most relevant domain knowledge chunks to inject into the
LLM system prompt — so only relevant knowledge is injected, not
the entire knowledge base.

Dependencies: faiss-cpu, sentence-transformers, numpy
"""

import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

# ---------------------------------------------------------------------------
# Module-level model (shared with embedding_store.py)
# ---------------------------------------------------------------------------

SEMANTIC_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# Module-level FAISS index and chunk store
# ---------------------------------------------------------------------------

semantic_index = None        # faiss.IndexFlatIP (inner product = cosine on normalized vectors)
semantic_chunks = []         # list of dicts: {"key": str, "text": str}
EMBEDDING_DIM = 384


# ---------------------------------------------------------------------------
# 1. Chunk the knowledge base
# ---------------------------------------------------------------------------

def chunk_knowledge_base(knowledge: dict) -> list:
    chunks = []

    def add(key, text):
        chunks.append({"key": key, "text": str(text)})

    # Pipeline stages
    for stage, info in knowledge.get("pipeline_stages", {}).items():
        add(
            f"pipeline_stage:{stage}",
            f"Stage {stage}: {info['description']} Common failures: {info['common_failures']}"
        )

    # File status codes
    for code, info in knowledge.get("file_status_codes", {}).items():
        add(
            f"status_code:{code}",
            f"FILE_STATUS_CD {code} means {info['label']}: {info['description']} Action: {info['action']}"
        )

    # Record type semantics — stronger text for better semantic retrieval
    rec = knowledge.get("record_type_semantics", {})
    for field in ["FAIL_REC_CNT", "REJ_REC_CNT", "SKIP_REC_CNT", "SCS_REC_CNT", "TOT_REC_CNT"]:
        if field in rec:
            info = rec[field]
            add(
                f"record_type:{field}",
                f"Record type {field} — failed vs rejected vs skipped records: "
                f"{info['meaning']} Implication: {info['implication']} Action: {info['action']}"
            )
    if "critical_distinction" in rec:
        dist = rec["critical_distinction"]
        add(
            "record_type:critical_distinction",
            f"Critical distinction between failed rejected skipped records: {dist}"
        )

    # Health flag meanings
    for flag, info in knowledge.get("health_flag_meanings", {}).items():
        if isinstance(info, dict):
            add(
                f"health_flag:{flag}",
                f"Health flag {flag}: {info['meaning']} Threshold: {info['threshold']} Action: {info['action']}"
            )
        else:
            add(f"health_flag:{flag}", str(info))

    # LOB glossary
    for lob, info in knowledge.get("lob_glossary", {}).items():
        add(
            f"lob:{lob}",
            f"LOB {lob}: {info['description']} Compliance burden: {info['compliance_burden']}. {info['notes']}"
        )

    # ROS table columns
    for col, desc in knowledge.get("ros_table_columns", {}).items():
        add(f"ros_column:{col}", f"ROS column {col}: {desc}")

    # Markets table columns
    for col, desc in knowledge.get("markets_table_columns", {}).items():
        add(f"markets_column:{col}", f"Markets column {col}: {desc}")

    # Derived columns
    for col, desc in knowledge.get("derived_columns", {}).items():
        add(f"derived_column:{col}", f"Derived column {col}: {desc}")

    # Cross layer join
    join_info = knowledge.get("cross_layer_join", {})
    add(
        "cross_layer_join",
        f"Join condition: {join_info.get('join_condition')}. "
        f"Use case: {join_info.get('use_case')} "
        f"Note: {join_info.get('important_note')}"
    )

    # Anomaly detection rules
    for rule, desc in knowledge.get("anomaly_detection_rules", {}).items():
        add(f"anomaly_rule:{rule}", f"Anomaly rule {rule}: {desc}")

    # Web search triggers
    for trigger, desc in knowledge.get("web_search_triggers", {}).items():
        add(f"web_search_trigger:{trigger}", f"Web search trigger {trigger}: {desc}")

    return chunks


# ---------------------------------------------------------------------------
# 2. Build FAISS index
# ---------------------------------------------------------------------------

def build_semantic_index(knowledge_path: str = "domain_knowledge.json") -> None:
    global semantic_index, semantic_chunks

    with open(knowledge_path, "r", encoding="utf-8") as f:
        knowledge = json.load(f)

    semantic_chunks = chunk_knowledge_base(knowledge)

    texts = [chunk["text"] for chunk in semantic_chunks]
    embeddings = SEMANTIC_MODEL.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    # Normalize for cosine similarity via inner product
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    embeddings = embeddings / norms
    embeddings = embeddings.astype(np.float32)

    semantic_index = faiss.IndexFlatIP(EMBEDDING_DIM)
    semantic_index.add(embeddings)

    print(f"[semantic_store] FAISS index built: {len(semantic_chunks)} chunks indexed.")


# ---------------------------------------------------------------------------
# 3. Search semantic index
# ---------------------------------------------------------------------------

def search_semantic_chunks(query_text: str, top_k: int = 5) -> list:
    if semantic_index is None or len(semantic_chunks) == 0:
        print("[semantic_store] WARNING: Index not built. Call build_semantic_index() first.")
        return []

    query_vec = SEMANTIC_MODEL.encode(query_text, convert_to_numpy=True)
    norm = np.linalg.norm(query_vec)
    if norm > 0:
        query_vec = query_vec / norm
    query_vec = query_vec.astype(np.float32).reshape(1, -1)

    k = min(top_k, len(semantic_chunks))
    scores, indices = semantic_index.search(query_vec, k)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx >= 0:
            results.append({
                "key": semantic_chunks[idx]["key"],
                "text": semantic_chunks[idx]["text"],
                "score": float(score)
            })

    return results


# ---------------------------------------------------------------------------
# 4. Format semantic chunks for LLM prompt injection
# ---------------------------------------------------------------------------

def format_semantic_chunks_for_prompt(chunks: list) -> str:
    if not chunks:
        return "No relevant domain knowledge found."

    lines = []
    for chunk in chunks:
        lines.append(f"[{chunk['key']}]\n{chunk['text']}")

    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# 5. __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 62)
    print("RosterIQ - Semantic Store Self-Test")
    print("=" * 62)

    build_semantic_index("domain_knowledge.json")
    print(f"[test] Total chunks in index: {len(semantic_chunks)}")

    # Print all chunk keys so we can verify record_type chunks are present
    record_type_keys = [c["key"] for c in semantic_chunks if c["key"].startswith("record_type")]
    print(f"\n[test] Record type chunks found: {record_type_keys}")

    # Test 1 — FAIL vs REJ distinction query
    query1 = "What is the difference between failed records and rejected records?"
    results1 = search_semantic_chunks(query1, top_k=3)
    print(f"\n[test] Query 1: '{query1}'")
    for r in results1:
        print(f"  [{r['key']}] score={r['score']:.4f}")
        print(f"  {r['text'][:120]}...")

    # Test 2 — stuck RO query
    query2 = "Why is an RO stuck in DART generation stage?"
    results2 = search_semantic_chunks(query2, top_k=3)
    print(f"\n[test] Query 2: '{query2}'")
    for r in results2:
        print(f"  [{r['key']}] score={r['score']:.4f}")
        print(f"  {r['text'][:120]}...")

    # Test 3 — market threshold query
    query3 = "What does it mean when a market is below threshold?"
    results3 = search_semantic_chunks(query3, top_k=3)
    print(f"\n[test] Query 3: '{query3}'")
    for r in results3:
        print(f"  [{r['key']}] score={r['score']:.4f}")
        print(f"  {r['text'][:120]}...")

    # Test 4 — format for prompt
    print("\n[test] Formatted prompt output for Query 1:")
    print(format_semantic_chunks_for_prompt(results1))

    # Test 5 — empty index guard
    original_index = semantic_index
    semantic_index = None
    empty_result = search_semantic_chunks("test query")
    assert empty_result == [], "Expected empty list when index is None"
    semantic_index = original_index
    print("\n[PASS] Empty index guard works correctly.")

    print("\n[OK] All semantic store tests passed.")
    print("=" * 62)