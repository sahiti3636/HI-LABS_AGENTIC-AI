"""
intent_classifier.py
====================
RosterIQ intent classifier — loads fine-tuned distilbert from ./intent_model/
Falls back to bart-large-mnli if fine-tuned model not found.
"""

import json
import os
import torch
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_DIR          = "./intent_model"
FALLBACK_MODEL     = "facebook/bart-large-mnli"
CONFIDENCE_THRESHOLD = 0.50
DEVICE             = "cpu"

INTENT_LABELS = [
    "data_query", "run_procedure", "global_stat", "memory_recall",
    "web_search", "visualization", "procedure_update", "multi_step",
]

# ---------------------------------------------------------------------------
# Load fine-tuned model
# ---------------------------------------------------------------------------

_model     = None
_tokenizer = None
_label_map = None
_use_bart  = False

if os.path.exists(MODEL_DIR) and os.path.exists(os.path.join(MODEL_DIR, "label_map.json")):
    try:
        print(f"[INFO] Loading fine-tuned intent classifier from {MODEL_DIR}...")
        _tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_DIR)
        _model     = DistilBertForSequenceClassification.from_pretrained(MODEL_DIR)
        _model.eval()
        with open(os.path.join(MODEL_DIR, "label_map.json")) as f:
            _label_map = {int(k): v for k, v in json.load(f).items()}
        print("[INFO] Fine-tuned intent classifier loaded ✓")
    except Exception as e:
        print(f"[WARN] Could not load fine-tuned model: {e}")
        print("[INFO] Falling back to bart-large-mnli...")
        _use_bart = True
else:
    print("[WARN] Fine-tuned model not found. Run train_intent_classifier.py first.")
    print("[INFO] Falling back to bart-large-mnli...")
    _use_bart = True

# Load bart fallback if needed
_bart_classifier = None
if _use_bart:
    try:
        from transformers import pipeline as hf_pipeline
        _bart_classifier = hf_pipeline(
            "zero-shot-classification",
            model=FALLBACK_MODEL,
            device=DEVICE,
        )
        print("[INFO] Fallback bart-large-mnli loaded ✓")
    except Exception as e:
        print(f"[ERROR] Could not load fallback model: {e}")

BART_INTENT_LABELS = {
    "data_query":       "The user wants to query or retrieve data from the database",
    "run_procedure":    "The user wants to run or execute a named procedure",
    "global_stat":      "The user wants a high-level system summary or overall statistics",
    "memory_recall":    "The user wants to recall something from a previous conversation",
    "web_search":       "The user wants to search the internet for external information",
    "visualization":    "The user wants to see a chart or graph",
    "procedure_update": "The user wants to update or modify a procedure or threshold",
    "multi_step":       "The user wants to perform multiple actions in one request",
}
_BART_LABEL_TO_KEY = {v: k for k, v in BART_INTENT_LABELS.items()}

# ---------------------------------------------------------------------------
# classify_intent
# ---------------------------------------------------------------------------

def classify_intent(query: str) -> dict:
    """
    Classify a natural language query into one of 8 RosterIQ intent categories.
    Priority: 1) Gemini few-shot  2) DistilBERT fine-tuned  3) BART fallback
    """

    # --- PRIMARY: Gemini few-shot path ---
    try:
        import google.generativeai as genai
        import json as _json
        import os
        _gkey = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if _gkey:
            genai.configure(api_key=_gkey)
            _gmodel = genai.GenerativeModel('gemini-flash-latest')
            _PROMPT = """
You are the central intent router for RosterIQ, a healthcare provider roster pipeline platform.
Classify the user query into ONE intent. Output ONLY JSON: {{"intent": "<intent_name>"}}

INTENTS:
- "global_stat": Simple aggregate metrics — counts, averages, totals, single numbers.
- "data_query": Retrieve specific records, filter rows, list organizations or files.
- "run_procedure": Run a named workflow or pipeline procedure.
- "visualization": Create a chart, graph, or visual dashboard.
- "multi_step": Complex multi-part analysis requiring sequential steps.
- "memory_recall": Recall a previous conversation or prior analysis.
- "web_search": Find external information online.
- "procedure_update": Update, modify, or create a procedure or threshold.

EXAMPLES:
User: "How many ROs are stuck?" → {{"intent": "global_stat"}}
User: "Show me stuck ROs in Kansas" → {{"intent": "data_query"}}
User: "Run the market health diagnostic" → {{"intent": "run_procedure"}}
User: "What did we find about Florida before?" → {{"intent": "memory_recall"}}
User: "Draw a chart of rejection rates" → {{"intent": "visualization"}}
User: "Search for CMS compliance updates" → {{"intent": "web_search"}}

User: "{query}"
""".format(query=query)
            response = _gmodel.generate_content(_PROMPT)
            text = response.text.strip()
            if '```' in text:
                text = text.split('```')[-2].replace('json','').strip()
            parsed = _json.loads(text)
            intent = parsed.get('intent', 'data_query')
            valid = {"data_query","run_procedure","global_stat","memory_recall",
                     "web_search","visualization","procedure_update","multi_step"}
            if intent not in valid:
                intent = 'data_query'
            return {
                "intent": intent, "confidence": 1.0,
                "all_scores": {intent: 1.0},
                "used_fallback": False, "model": "gemini-few-shot", "query": query,
            }
    except Exception as _e:
        print(f"[WARN] Gemini intent classification failed: {_e}. Falling back.")

    # --- Fine-tuned distilbert path ---
    if _model is not None and _tokenizer is not None:
        inputs = _tokenizer(
            query,
            truncation=True,
            padding="max_length",
            max_length=64,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = _model(**inputs)
            probs   = torch.softmax(outputs.logits, dim=-1)[0]

        scores     = {_label_map[i]: round(probs[i].item(), 4) for i in range(len(_label_map))}
        all_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))
        top_intent = list(all_scores.keys())[0]
        top_score  = list(all_scores.values())[0]

        used_fallback = top_score < CONFIDENCE_THRESHOLD
        final_intent  = "data_query" if used_fallback else top_intent

        return {
            "intent":        final_intent,
            "confidence":    top_score,
            "all_scores":    all_scores,
            "used_fallback": used_fallback,
            "model":         "distilbert-finetuned",
            "query":         query,
        }

    # --- Bart fallback path ---
    if _bart_classifier is not None:
        candidate_labels = list(BART_INTENT_LABELS.values())
        result = _bart_classifier(query, candidate_labels=candidate_labels, multi_label=False)
        raw_scores = {
            _BART_LABEL_TO_KEY[label]: round(score, 4)
            for label, score in zip(result["labels"], result["scores"])
        }
        all_scores = dict(sorted(raw_scores.items(), key=lambda x: x[1], reverse=True))
        top_intent = list(all_scores.keys())[0]
        top_score  = list(all_scores.values())[0]
        used_fallback = top_score < CONFIDENCE_THRESHOLD
        final_intent  = "data_query" if used_fallback else top_intent

        return {
            "intent":        final_intent,
            "confidence":    top_score,
            "all_scores":    all_scores,
            "used_fallback": used_fallback,
            "model":         "bart-fallback",
            "query":         query,
        }

    # --- No model available ---
    return {
        "intent":        "data_query",
        "confidence":    1.0,
        "all_scores":    {k: 0.0 for k in INTENT_LABELS},
        "used_fallback": True,
        "model":         "hardcoded-fallback",
        "query":         query,
    }


# ---------------------------------------------------------------------------
# batch_classify
# ---------------------------------------------------------------------------

def batch_classify(queries: list) -> list:
    total = len(queries)
    results = []
    for idx, query in enumerate(queries, start=1):
        print(f"  [{idx}/{total}] classifying: {query[:60]}{'...' if len(query) > 60 else ''}")
        results.append(classify_intent(query))
    return results


# ---------------------------------------------------------------------------
# Test block
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    EXPECTED_INTENTS = [
        "data_query", "data_query", "data_query",
        "run_procedure", "run_procedure", "run_procedure",
        "global_stat", "global_stat", "global_stat",
        "memory_recall", "memory_recall", "memory_recall",
        "web_search", "web_search", "web_search",
        "visualization", "visualization", "visualization",
        "procedure_update", "procedure_update", "procedure_update",
        "multi_step", "multi_step", "multi_step",
    ]

    TEST_QUERIES = [
    # data_query
    "Which organizations have the most failed ROs?",
    "Show me all ROs stuck in mapping stage",
    "What is the health score for Florida?",
    # run_procedure
    "Kick off the market health diagnostic",
    "Trigger the record audit for all orgs",
    "Start the retry effectiveness workflow",
    # global_stat
    "Give me a full system overview",
    "What are the aggregate stats for all markets?",
    "What is the total pipeline success rate?",
    # memory_recall
    "What did we analyze about Florida before?",
    "Remind me what we found about DART issues",
    "What were the prior results for Humana?",
    # web_search
    "Find the latest CMS provider data rules",
    "Search online for Medicaid compliance updates",
    "Look up recent changes to EDI standards",
    # visualization
    "Draw me a chart of rejection rates",
    "Show a graph of stuck ROs by market",
    "Create a visual of pipeline bottlenecks",
    # procedure_update
    "Set the anomaly threshold to 3 standard deviations",
    "Edit the triage procedure to add a LOB filter",
    "Adjust the health score cutoff to 75",
    # multi_step
    "Get failure stats for Florida and then chart them",
    "Run the audit then look up compliance fixes online",
    "Show rejection rates by org and then plot a comparison",
]

    print("\n" + "=" * 72)
    print("  RosterIQ — Intent Classifier Test Suite (24 queries)")
    print("=" * 72)
    print(f"  {'QUERY':<55}  {'INTENT':<18}  {'CONF':>6}  {'MODEL':<20}  OK")
    print("-" * 72)

    intent_order = INTENT_LABELS
    per_intent_correct = {k: 0 for k in intent_order}
    per_intent_total   = {k: 0 for k in intent_order}
    total_correct = 0

    for query, expected in zip(TEST_QUERIES, EXPECTED_INTENTS):
        res       = classify_intent(query)
        predicted = res["intent"]
        conf      = res["confidence"]
        model_src = res["model"]
        marker    = "✓" if predicted == expected else "✗"
        q_display = (query[:52] + "...") if len(query) > 55 else query

        print(f"  {q_display:<55}  {predicted:<18}  {conf:>6.4f}  {model_src:<20}  {marker}")

        per_intent_total[expected] += 1
        if predicted == expected:
            per_intent_correct[expected] += 1
            total_correct += 1

    print("\n" + "=" * 72)
    print("  Accuracy Summary")
    print("-" * 72)
    print(f"  {'INTENT':<20}  {'CORRECT':>7}  {'TOTAL':>5}  {'RATE':>6}")
    print("-" * 72)
    for intent in intent_order:
        c = per_intent_correct[intent]
        t = per_intent_total[intent]
        print(f"  {intent:<20}  {c:>7}  {t:>5}  {c/t*100:.0f}%")
    print("-" * 72)
    print(f"  {'OVERALL':<20}  {total_correct:>7}  {'24':>5}  {total_correct/24*100:.0f}%")
    print("=" * 72 + "\n")