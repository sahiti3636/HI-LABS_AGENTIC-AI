"""
embedding_store.py
------------------
Semantic embedding layer for RosterIQ's episodic memory system.

Every episode written to SQLite also gets embedded here as a normalised
sentence-embedding vector.  Incoming queries are similarly embedded and
ranked by cosine similarity (= dot product of normalised vectors) to
retrieve the past episodes most semantically relevant to the new query.

Architecture
------------
    episodic_memory.py  <-- persistent storage  (SQLite)
    embedding_store.py  <-- in-memory semantics  (numpy + SentenceTransformers)

The two layers are kept in sync via:
    - add_episode_embedding()       : called after every write_episode()
    - load_existing_embeddings_from_db() : called on startup to rebuild from SQLite

Model: sentence-transformers/all-MiniLM-L6-v2  (384-dim embeddings)
"""

import sqlite3
import json

import numpy as np
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# Module-level model (loaded once)
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

# ---------------------------------------------------------------------------
# In-memory vector store
# ---------------------------------------------------------------------------

vector_store: dict = {
    "episode_ids": [],  # list[int]  — episodic_memory row ids
    "vectors": None,    # np.ndarray of shape (N, 384), or None when empty
}


# ---------------------------------------------------------------------------
# 3. embed_text
# ---------------------------------------------------------------------------

def embed_text(text: str) -> np.ndarray:
    """
    Embed *text* with the module-level EMBEDDING_MODEL and return a
    normalised 1-D numpy array of shape (384,).

    Normalisation (divide by L2 norm) means that subsequent dot products
    between two embedded vectors equal their cosine similarity.

    Args:
        text: Any string to embed.

    Returns:
        Normalised embedding vector of dtype float32, shape (384,).
    """
    vector: np.ndarray = EMBEDDING_MODEL.encode(text, convert_to_numpy=True)
    norm = np.linalg.norm(vector)
    if norm > 0.0:
        vector = vector / norm
    return vector


# ---------------------------------------------------------------------------
# 4. add_episode_embedding
# ---------------------------------------------------------------------------

def add_episode_embedding(
    episode_id: int,
    query_text: str,
    findings_text: str,
) -> None:
    """
    Build and store an embedding for a single episode.

    The embedding is computed from the concatenation of *query_text* and
    *findings_text*, giving the vector store a rich semantic signal.

    Args:
        episode_id:    The SQLite row id from episodic_memory.
        query_text:    The user's natural-language query for this episode.
        findings_text: The agent's narrative findings for this episode.
    """
    combined = f"{query_text} {findings_text}"
    vector = embed_text(combined)  # shape (384,)

    vector_store["episode_ids"].append(episode_id)

    if vector_store["vectors"] is None:
        vector_store["vectors"] = vector.reshape(1, -1)
    else:
        vector_store["vectors"] = np.vstack(
            [vector_store["vectors"], vector.reshape(1, -1)]
        )


# ---------------------------------------------------------------------------
# 5. search_similar_episodes
# ---------------------------------------------------------------------------

def search_similar_episodes(
    query_text: str,
    top_k: int = 5,
) -> list:
    """
    Find the *top_k* most semantically similar episodes to *query_text*.

    Similarity is measured via cosine similarity, which reduces to a dot
    product because all stored vectors are L2-normalised.

    Args:
        query_text: Incoming natural-language query to match against.
        top_k:      Number of top results to return (default 5).

    Returns:
        A list of episode_ids (ints) ordered by similarity score descending.
        Returns an empty list if the vector store is empty.
    """
    if vector_store["vectors"] is None or len(vector_store["episode_ids"]) == 0:
        return []

    query_vector = embed_text(query_text)  # shape (384,)

    # Dot product of (384,) against (N, 384) -> (N,) similarity scores
    scores: np.ndarray = vector_store["vectors"].dot(query_vector)

    # Sort by descending similarity and take the top_k indices
    k = min(top_k, len(scores))
    top_indices = np.argsort(scores)[::-1][:k]

    return [vector_store["episode_ids"][i] for i in top_indices]


# ---------------------------------------------------------------------------
# 6. load_existing_embeddings_from_db
# ---------------------------------------------------------------------------

def load_existing_embeddings_from_db(
    db_path: str = "episodic_memory.db",
) -> None:
    """
    Rebuild the in-memory vector store from all rows in the SQLite
    episodic_memory table.

    Call this once on application startup so the embedding layer is
    consistent with the persisted episode history even after a restart.

    Args:
        db_path: Path to the SQLite database file.
    """
    # Reset the store before rebuilding
    vector_store["episode_ids"] = []
    vector_store["vectors"] = None

    select_sql = """
    SELECT id, query_text, findings_text
    FROM   episodic_memory
    ORDER BY id ASC
    """
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(select_sql).fetchall()
    except sqlite3.OperationalError:
        # Table does not exist yet — nothing to load
        print(f"[embedding_store] No episodic_memory table found in '{db_path}'. "
              "Starting with empty vector store.")
        return

    for row_id, query_text, findings_text in rows:
        add_episode_embedding(
            episode_id=row_id,
            query_text=query_text or "",
            findings_text=findings_text or "",
        )

    count = len(vector_store["episode_ids"])
    print(f"[embedding_store] Loaded {count} episode(s) from '{db_path}'.")


# ---------------------------------------------------------------------------
# 7. __main__ test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    from episodic_memory import init_episodic_db, write_episode

    DB_PATH = "embedding_store_test.db"

    # Clean slate
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("=" * 62)
    print("RosterIQ - Embedding Store Self-Test")
    print("=" * 62)

    # ── 1. Initialise DB and write 3 sample episodes ──────────────
    init_episodic_db(db_path=DB_PATH)

    ep1_id = write_episode(
        session_id="test-session",
        query_text="Show me gap rates for Kansas providers in Q1 2024",
        intent_classified="gap_analysis",
        sql_generated="SELECT state, COUNT(*) FROM roster_pipeline WHERE state='KS'",
        result_summary="Kansas had 142 provider gaps in Q1 2024.",
        entities_involved_dict={"states": ["KS"], "orgs": ["Org-A"], "ros": [], "markets": []},
        findings_text=(
            "Pipeline gaps in Kansas are concentrated in rural areas. "
            "Org-A shows the highest gap rate at 38%. "
            "Immediate credentialing backlog identified."
        ),
        chart_generated=True,
        db_path=DB_PATH,
    )

    ep2_id = write_episode(
        session_id="test-session",
        query_text="Compare Texas vs California provider coverage last month",
        intent_classified="coverage_comparison",
        sql_generated="SELECT state, AVG(coverage_pct) FROM roster_pipeline WHERE state IN ('TX','CA')",
        result_summary="TX avg coverage 74%, CA avg coverage 81%.",
        entities_involved_dict={"states": ["TX", "CA"], "orgs": [], "ros": ["RO-South"], "markets": []},
        findings_text=(
            "California outperforms Texas in overall provider coverage by 7 percentage points. "
            "RO-South should focus on closing Texas market gaps in urban areas."
        ),
        chart_generated=False,
        db_path=DB_PATH,
    )

    ep3_id = write_episode(
        session_id="test-session",
        query_text="Which markets have the highest provider attrition rate this quarter?",
        intent_classified="attrition_analysis",
        sql_generated="SELECT market, COUNT(*) FROM roster_pipeline WHERE status='terminated' GROUP BY market",
        result_summary="Dallas and Phoenix have the highest attrition at 22% and 19%.",
        entities_involved_dict={"states": ["TX", "AZ"], "orgs": [], "ros": [], "markets": ["Dallas", "Phoenix"]},
        findings_text=(
            "Provider attrition is surging in Dallas and Phoenix this quarter. "
            "Main driver is contract non-renewals and burnout in specialty care. "
            "Retention incentives recommended."
        ),
        chart_generated=True,
        db_path=DB_PATH,
    )

    print(f"\n[test] Episodes written: ids = {ep1_id}, {ep2_id}, {ep3_id}")

    # ── 2. Add embeddings for all 3 ───────────────────────────────
    print("\n[test] Building embeddings...")
    add_episode_embedding(ep1_id,
                          "Show me gap rates for Kansas providers in Q1 2024",
                          "Pipeline gaps in Kansas are concentrated in rural areas. "
                          "Org-A shows the highest gap rate at 38%. "
                          "Immediate credentialing backlog identified.")

    add_episode_embedding(ep2_id,
                          "Compare Texas vs California provider coverage last month",
                          "California outperforms Texas in overall provider coverage by 7 percentage points. "
                          "RO-South should focus on closing Texas market gaps in urban areas.")

    add_episode_embedding(ep3_id,
                          "Which markets have the highest provider attrition rate this quarter?",
                          "Provider attrition is surging in Dallas and Phoenix this quarter. "
                          "Main driver is contract non-renewals and burnout in specialty care. "
                          "Retention incentives recommended.")

    n_stored = len(vector_store["episode_ids"])
    print(f"[test] Vectors stored: {n_stored}  (shape: {vector_store['vectors'].shape})")

    # ── 3. Search Test 1 — gap / credentialing query ──────────────
    query_a = "Are there any credentialing gaps or provider shortages in rural Kansas?"
    results_a = search_similar_episodes(query_a, top_k=3)
    print(f"\n[test] Query A: '{query_a}'")
    print(f"  Top episode ids (most -> least similar): {results_a}")
    assert results_a[0] == ep1_id, (
        f"Expected episode {ep1_id} to rank first for query A, got {results_a}"
    )
    print(f"  [PASS] Episode {ep1_id} (Kansas gap analysis) ranked #1 as expected.")

    # ── 4. Search Test 2 — attrition query ───────────────────────
    query_b = "Which regions are losing the most providers due to attrition or burnout?"
    results_b = search_similar_episodes(query_b, top_k=3)
    print(f"\n[test] Query B: '{query_b}'")
    print(f"  Top episode ids (most -> least similar): {results_b}")
    assert results_b[0] == ep3_id, (
        f"Expected episode {ep3_id} to rank first for query B, got {results_b}"
    )
    print(f"  [PASS] Episode {ep3_id} (attrition analysis) ranked #1 as expected.")

    # ── 5. Test load_existing_embeddings_from_db ─────────────────
    print("\n[test] Clearing vector store and reloading from DB...")
    vector_store["episode_ids"] = []
    vector_store["vectors"] = None

    load_existing_embeddings_from_db(db_path=DB_PATH)

    reloaded_count = len(vector_store["episode_ids"])
    assert reloaded_count == 3, (
        f"Expected 3 episodes after reload, got {reloaded_count}"
    )
    print(f"  [PASS] Reloaded {reloaded_count} episodes — count matches original.")
    print(f"  Vector store shape after reload: {vector_store['vectors'].shape}")

    # ── Cleanup ───────────────────────────────────────────────────
    os.remove(DB_PATH)
    print("\n[OK] All embedding store tests passed.")
    print("=" * 62)
