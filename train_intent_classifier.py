"""
train_intent_classifier.py
==========================
Fine-tunes distilbert-base-uncased on RosterIQ intent classification.
Saves trained model to ./intent_model/ for use by intent_classifier.py.
Run once before using the classifier.
"""

import json
import os
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import torch
from torch.utils.data import Dataset, DataLoader
from torch.optim import AdamW
from transformers import (
    DistilBertTokenizerFast,
    DistilBertForSequenceClassification,
    get_linear_schedule_with_warmup,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

MODEL_NAME     = "distilbert-base-uncased"
TRAINING_FILE  = "training_data.json"
OUTPUT_DIR     = "./intent_model"
MAX_LEN        = 64
BATCH_SIZE     = 16
EPOCHS         = 5
LEARNING_RATE  = 2e-5
TEST_SIZE      = 0.15
RANDOM_SEED    = 42

INTENT_LABELS = [
    "data_query",
    "run_procedure",
    "global_stat",
    "memory_recall",
    "web_search",
    "visualization",
    "procedure_update",
    "multi_step",
]

# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class IntentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len):
        self.encodings = tokenizer(
            texts,
            truncation=True,
            padding="max_length",
            max_length=max_len,
            return_tensors="pt",
        )
        self.labels = torch.tensor(labels, dtype=torch.long)

    def __len__(self):
        return len(self.labels)

    def __getitem__(self, idx):
        return {
            "input_ids":      self.encodings["input_ids"][idx],
            "attention_mask": self.encodings["attention_mask"][idx],
            "labels":         self.labels[idx],
        }

# ---------------------------------------------------------------------------
# Main training
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    # Load data
    print("[INFO] Loading training data...")
    with open(TRAINING_FILE) as f:
        data = json.load(f)

    texts  = [d["text"]  for d in data]
    labels = [d["label"] for d in data]

    # Encode labels to integers
    le = LabelEncoder()
    le.fit(INTENT_LABELS)
    label_ids = le.transform(labels).tolist()

    # Save label encoder mapping
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    label_map = {i: label for i, label in enumerate(le.classes_)}
    with open(os.path.join(OUTPUT_DIR, "label_map.json"), "w") as f:
        json.dump(label_map, f, indent=2)
    print(f"[INFO] Label map: {label_map}")

    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        texts, label_ids,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=label_ids,
    )
    print(f"[INFO] Train: {len(X_train)} | Test: {len(X_test)}")

    # Tokenizer
    print(f"[INFO] Loading tokenizer ({MODEL_NAME})...")
    tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_NAME)

    # Datasets
    train_dataset = IntentDataset(X_train, y_train, tokenizer, MAX_LEN)
    test_dataset  = IntentDataset(X_test,  y_test,  tokenizer, MAX_LEN)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    test_loader  = DataLoader(test_dataset,  batch_size=BATCH_SIZE, shuffle=False)

    # Model
    print(f"[INFO] Loading model ({MODEL_NAME})...")
    model = DistilBertForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(INTENT_LABELS),
    )
    device = torch.device("cpu")
    model.to(device)

    # Optimizer + scheduler
    optimizer = AdamW(model.parameters(), lr=LEARNING_RATE)
    total_steps = len(train_loader) * EPOCHS
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=total_steps // 10,
        num_training_steps=total_steps,
    )

    # ---------------------------------------------------------------------------
    # Training loop
    # ---------------------------------------------------------------------------
    print(f"\n[INFO] Starting training — {EPOCHS} epochs on CPU...")
    print("=" * 60)

    for epoch in range(1, EPOCHS + 1):
        model.train()
        total_loss = 0
        correct = 0
        total = 0

        for batch_idx, batch in enumerate(train_loader, 1):
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels_batch   = batch["labels"].to(device)

            optimizer.zero_grad()
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels_batch,
            )
            loss = outputs.loss
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            preds = outputs.logits.argmax(dim=-1)
            correct += (preds == labels_batch).sum().item()
            total += len(labels_batch)

            if batch_idx % 10 == 0:
                print(f"  Epoch {epoch} | Batch {batch_idx}/{len(train_loader)} "
                      f"| Loss: {loss.item():.4f} "
                      f"| Train Acc: {correct/total*100:.1f}%")

        avg_loss = total_loss / len(train_loader)
        train_acc = correct / total * 100
        print(f"\n  Epoch {epoch} complete | Avg Loss: {avg_loss:.4f} | Train Acc: {train_acc:.1f}%\n")

    # ---------------------------------------------------------------------------
    # Evaluation
    # ---------------------------------------------------------------------------
    print("=" * 60)
    print("[INFO] Evaluating on test set...")
    model.eval()
    all_preds = []
    all_true  = []

    with torch.no_grad():
        for batch in test_loader:
            input_ids      = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels_batch   = batch["labels"].to(device)

            outputs = model(input_ids=input_ids, attention_mask=attention_mask)
            preds   = outputs.logits.argmax(dim=-1)
            all_preds.extend(preds.cpu().numpy())
            all_true.extend(labels_batch.cpu().numpy())

    all_preds = np.array(all_preds)
    all_true  = np.array(all_true)
    accuracy  = (all_preds == all_true).mean() * 100

    print(f"\n  Test Accuracy: {accuracy:.1f}%\n")
    print(classification_report(
        all_true, all_preds,
        target_names=[label_map[i] for i in sorted(label_map)],
    ))

    # ---------------------------------------------------------------------------
    # Save model
    # ---------------------------------------------------------------------------
    print(f"[INFO] Saving model to {OUTPUT_DIR}...")
    model.save_pretrained(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)
    print(f"[INFO] Model saved ✓")
    print(f"\n[INFO] Training complete. Run intent_classifier.py to use the model.")