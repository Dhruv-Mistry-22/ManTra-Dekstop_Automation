#!/usr/bin/env python
"""
benchmark.py – Mantra AI Desktop Automation V2
===============================================
Evaluation framework for comparing V1 (keyword scanning) vs V2
(sentence-transformers cosine similarity) intent classification.

Usage
-----
    python benchmark.py --csv test_utterances.csv
    python benchmark.py --csv test_utterances.csv --output results.csv --v2-threshold 0.40

CSV format (required columns)
------------------------------
    utterance, true_intent, true_entity, category, phrasing_style

Output
------
    - Per-category precision / recall / F1 (sklearn classification_report)
    - Overall accuracy comparison table: V1 vs V2
    - Latency percentiles: p50, p95, max for each method
    - Detailed per-row results saved to --output (default: results.csv)
    - Research-ready summary table printed to stdout
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
import logging
from pathlib import Path
from typing import Optional

import numpy as np

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")

# ---------------------------------------------------------------------------
# V1 — Keyword Scanning
# Mirrors _keyword_fallback() in intent_module.py plus extended rules
# from the full V1 design.  All rules are pure set-membership checks.
# ---------------------------------------------------------------------------

# Ordered rule table: (required_keywords, forbidden_keywords, intent)
# Each entry is checked in order; first match wins.
_V1_RULES: list[tuple[frozenset, frozenset, str]] = [
    # Application management
    (frozenset({"open"}),       frozenset({"file", "folder"}), "open_app"),
    (frozenset({"launch"}),     frozenset(),                   "open_app"),
    (frozenset({"start"}),      frozenset({"recording"}),      "open_app"),
    (frozenset({"switch"}),     frozenset(),                   "open_app"),
    (frozenset({"close"}),      frozenset({"file", "folder"}), "close_app"),
    (frozenset({"quit"}),       frozenset(),                   "close_app"),
    (frozenset({"exit"}),       frozenset(),                   "close_app"),
    (frozenset({"list", "apps"}),     frozenset(),             "list_apps"),
    (frozenset({"running", "apps"}),  frozenset(),             "list_apps"),
    (frozenset({"active", "window"}), frozenset(),             "get_active_window"),
    # File / folder management
    (frozenset({"create", "file"}),   frozenset(),             "create_file"),
    (frozenset({"make", "file"}),     frozenset(),             "create_file"),
    (frozenset({"new", "file"}),      frozenset(),             "create_file"),
    (frozenset({"create", "folder"}), frozenset(),             "create_folder"),
    (frozenset({"create", "directory"}), frozenset(),          "create_folder"),
    (frozenset({"make", "folder"}),   frozenset(),             "create_folder"),
    (frozenset({"open", "file"}),     frozenset(),             "open_file_folder"),
    (frozenset({"open", "folder"}),   frozenset(),             "open_file_folder"),
    (frozenset({"rename", "file"}),   frozenset(),             "rename_file"),
    (frozenset({"rename", "folder"}), frozenset(),             "rename_folder"),
    (frozenset({"delete", "file"}),   frozenset(),             "delete_file"),
    (frozenset({"remove", "file"}),   frozenset(),             "delete_file"),
    (frozenset({"delete", "folder"}), frozenset(),             "delete_folder"),
    (frozenset({"search"}),           frozenset(),             "search_files"),
    (frozenset({"find", "file"}),     frozenset(),             "search_files"),
    (frozenset({"move", "file"}),     frozenset(),             "move_file"),
    (frozenset({"list", "files"}),    frozenset(),             "list_files"),
    (frozenset({"show", "files"}),    frozenset(),             "list_files"),
    # System control
    (frozenset({"shutdown"}),         frozenset(),             "shutdown_system"),
    (frozenset({"turn", "off"}),      frozenset(),             "shutdown_system"),
    (frozenset({"restart"}),          frozenset(),             "restart_system"),
    (frozenset({"reboot"}),           frozenset(),             "restart_system"),
    (frozenset({"lock"}),             frozenset(),             "lock_system"),
    (frozenset({"logout"}),           frozenset(),             "logout_user"),
    (frozenset({"log", "out"}),       frozenset(),             "logout_user"),
    (frozenset({"sleep"}),            frozenset(),             "sleep_system"),
    (frozenset({"hibernate"}),        frozenset(),             "sleep_system"),
    (frozenset({"volume", "up"}),     frozenset(),             "increase_volume"),
    (frozenset({"louder"}),           frozenset(),             "increase_volume"),
    (frozenset({"volume", "down"}),   frozenset(),             "decrease_volume"),
    (frozenset({"quieter"}),          frozenset(),             "decrease_volume"),
    (frozenset({"mute"}),             frozenset(),             "mute_volume"),
    (frozenset({"system", "info"}),   frozenset(),             "get_system_info"),
    (frozenset({"specs"}),            frozenset(),             "get_system_info"),
    # Text input
    (frozenset({"type"}),             frozenset(),             "type_text"),
    (frozenset({"write"}),            frozenset(),             "type_text"),
    (frozenset({"copy"}),             frozenset(),             "copy_text"),
    (frozenset({"paste"}),            frozenset(),             "paste_text"),
    (frozenset({"select", "all"}),    frozenset(),             "select_all"),
    (frozenset({"undo"}),             frozenset(),             "undo_action"),
    (frozenset({"redo"}),             frozenset(),             "redo_action"),
    # Macro
    (frozenset({"start", "recording"}), frozenset(),           "record_macro"),
    (frozenset({"record", "macro"}),    frozenset(),           "record_macro"),
    (frozenset({"stop", "recording"}),  frozenset(),           "stop_macro"),
    (frozenset({"play", "macro"}),      frozenset(),           "play_macro"),
    (frozenset({"run", "macro"}),       frozenset(),           "play_macro"),
    (frozenset({"list", "macros"}),     frozenset(),           "list_macros"),
    # Screen
    (frozenset({"read", "screen"}),     frozenset(),           "read_screen"),
    (frozenset({"screen", "text"}),     frozenset(),           "read_screen"),
]

# Known app keywords (mirrors nlp_module._KNOWN_APP_KEYWORDS)
_KNOWN_APPS = {
    "chrome", "firefox", "edge", "opera", "brave", "safari",
    "notepad", "wordpad", "word", "excel", "powerpoint", "outlook",
    "vlc", "discord", "telegram", "whatsapp", "slack", "teams",
    "spotify", "steam", "blender", "gimp", "pycharm", "intellij",
    "calculator", "paint", "zoom", "skype", "obs", "audacity",
    "7zip", "winrar", "putty", "filezilla", "thunderbird",
    "vs", "code", "visual", "studio", "atom", "sublime",
}


def _v1_predict_intent(utterance: str) -> str:
    """V1 keyword-scanning intent classifier."""
    words = set(utterance.lower().split())
    for required, forbidden, intent in _V1_RULES:
        if required.issubset(words) and not forbidden.intersection(words):
            return intent
    # Last-resort: known app heuristic (mirrors execution_module unknown branch)
    if words.intersection(_KNOWN_APPS):
        return "open_app"
    return "unknown"


def _v1_predict_entity(utterance: str) -> Optional[str]:
    """V1 entity extractor: returns first known app token, else None."""
    words = utterance.lower().split()
    for w in words:
        if w in _KNOWN_APPS:
            return w
    import re
    m = re.search(r'\b([\w\-]+\.\w{2,5})\b', utterance.lower())
    if m:
        return m.group(1)
    return None


# ---------------------------------------------------------------------------
# V2 — Sentence-transformers cosine similarity
# Uses the same model + example library as the live intent_module.py.
# The model and embeddings are loaded once and reused across all rows.
# ---------------------------------------------------------------------------

_v2_model = None
_v2_embeddings = None
_v2_labels = None


def _load_v2_model(threshold: float = 0.40):
    """Load sentence-transformers model and pre-compute intent embeddings."""
    global _v2_model, _v2_embeddings, _v2_labels
    if _v2_model is not None:
        return _v2_model, _v2_embeddings, _v2_labels

    import os
    os.environ.setdefault("HF_HUB_OFFLINE", "1")

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise SystemExit(
            "[benchmark] sentence-transformers not installed.\n"
            "Run: pip install sentence-transformers"
        )

    print("[benchmark] Loading sentence-transformers model (one-time)...",
          flush=True)
    _v2_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)

    try:
        import sys, pathlib
        sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
        from modules.entity_aware_intent import build_normalized_embeddings
    except ImportError:
        raise SystemExit(
            "[benchmark] Cannot import build_normalized_embeddings from modules.entity_aware_intent.\n"
            "Ensure benchmark.py is run from the project root."
        )

    print("[benchmark] Pre-computing normalized intent embeddings...", flush=True)
    _v2_embeddings, _v2_labels = build_normalized_embeddings(_v2_model)

    print("[benchmark] Model ready.\n", flush=True)
    return _v2_model, _v2_embeddings, _v2_labels


def _v2_predict_intent(utterance: str, threshold: float) -> str:
    """V2 cosine-similarity intent classifier."""
    import torch
    from sentence_transformers import util as st_util

    model, embeddings = _v2_model, _v2_embeddings
    cmd_emb = model.encode(utterance, convert_to_tensor=True,
                           show_progress_bar=False)

    best_intent = "unknown"
    best_score = 0.0
    for intent, ex_embs in embeddings.items():
        scores = st_util.cos_sim(cmd_emb, ex_embs)
        ms = float(scores.max())
        if ms > best_score:
            best_score = ms
            best_intent = intent

    return best_intent if best_score >= threshold else "unknown"


def _v2_predict_entity(utterance: str) -> Optional[str]:
    """Entity extraction is identical between V1 and V2 (NLP module)."""
    return _v1_predict_entity(utterance)


# ---------------------------------------------------------------------------
# CSV Loading
# ---------------------------------------------------------------------------

REQUIRED_COLS = {"utterance", "true_intent", "true_entity",
                 "category", "phrasing_style"}


def load_csv(path: Path) -> list[dict]:
    """Load and validate the benchmark CSV."""
    if not path.exists():
        raise SystemExit(f"[benchmark] File not found: {path}")

    rows: list[dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("[benchmark] CSV appears to be empty.")
        missing = REQUIRED_COLS - {c.strip() for c in reader.fieldnames}
        if missing:
            raise SystemExit(
                f"[benchmark] CSV is missing required columns: {missing}\n"
                f"Expected: {REQUIRED_COLS}\n"
                f"Got:      {set(reader.fieldnames)}"
            )
        for i, row in enumerate(reader, start=2):  # row 1 = header
            rows.append({
                "utterance":     row["utterance"].strip(),
                "true_intent":   row["true_intent"].strip(),
                "true_entity":   row["true_entity"].strip() or None,
                "category":      row["category"].strip(),
                "phrasing_style": row["phrasing_style"].strip(),
            })

    if not rows:
        raise SystemExit("[benchmark] CSV has no data rows.")
    print(f"[benchmark] Loaded {len(rows)} test cases from {path}\n")
    return rows


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _entity_match(predicted: Optional[str], true: Optional[str]) -> bool:
    """Case-insensitive entity comparison; both None counts as correct."""
    if true is None or true == "":
        return True   # no ground-truth entity to check
    if predicted is None:
        return False
    return predicted.strip().lower() == true.strip().lower()


def run_evaluation(
    rows: list[dict],
    v2_threshold: float,
) -> tuple[list[dict], list[dict]]:
    """
    Run both classifiers over all rows.

    Returns:
        (v1_results, v2_results) — each is a list of result dicts with keys:
        utterance, category, phrasing_style, true_intent, true_entity,
        predicted_intent, predicted_entity, correct_intent, correct_entity,
        latency_ms
    """
    _load_v2_model(v2_threshold)   # ensure model is ready

    v1_results: list[dict] = []
    v2_results: list[dict] = []

    total = len(rows)
    for i, row in enumerate(rows, start=1):
        utt       = row["utterance"]
        t_intent  = row["true_intent"]
        t_entity  = row["true_entity"]
        category  = row["category"]
        phrasing  = row["phrasing_style"]

        print(f"\r  Evaluating {i}/{total}...", end="", flush=True)

        # ── V1 ────────────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        v1_intent = _v1_predict_intent(utt)
        v1_entity = _v1_predict_entity(utt)
        v1_lat    = (time.perf_counter() - t0) * 1000.0

        v1_results.append({
            "utterance":        utt,
            "category":         category,
            "phrasing_style":   phrasing,
            "true_intent":      t_intent,
            "true_entity":      t_entity,
            "predicted_intent": v1_intent,
            "predicted_entity": v1_entity,
            "correct_intent":   v1_intent == t_intent,
            "correct_entity":   _entity_match(v1_entity, t_entity),
            "latency_ms":       round(v1_lat, 4),
        })

        # ── V2 ────────────────────────────────────────────────────────────────
        t0 = time.perf_counter()
        try:
            from modules.entity_aware_intent import hybrid_predict
            v2_intent, v2_entity, _ = hybrid_predict(utt, _v2_model, _v2_embeddings, _v2_labels)
        except Exception:
            v2_intent = "unknown"
            v2_entity = ""
        v2_lat    = (time.perf_counter() - t0) * 1000.0

        v2_results.append({
            "utterance":        utt,
            "category":         category,
            "phrasing_style":   phrasing,
            "true_intent":      t_intent,
            "true_entity":      t_entity,
            "predicted_intent": v2_intent,
            "predicted_entity": v2_entity,
            "correct_intent":   v2_intent == t_intent,
            "correct_entity":   _entity_match(v2_entity, t_entity),
            "latency_ms":       round(v2_lat, 4),
        })

    print(f"\r  Evaluation complete ({total} rows).          ")
    return v1_results, v2_results


# ---------------------------------------------------------------------------
# Metrics computation
# ---------------------------------------------------------------------------

def _latency_percentiles(results: list[dict]) -> dict:
    lats = np.array([r["latency_ms"] for r in results])
    return {
        "p50":  round(float(np.percentile(lats, 50)),  4),
        "p95":  round(float(np.percentile(lats, 95)),  4),
        "max":  round(float(lats.max()),               4),
        "mean": round(float(lats.mean()),              4),
    }


def _accuracy(results: list[dict]) -> float:
    correct = sum(1 for r in results if r["correct_intent"])
    return round(correct / len(results) * 100, 2)


def _entity_accuracy(results: list[dict]) -> float:
    correct = sum(1 for r in results if r["correct_entity"])
    return round(correct / len(results) * 100, 2)


def compute_metrics(results: list[dict], method_name: str) -> None:
    """Print sklearn classification_report broken down by category."""
    from sklearn.metrics import classification_report

    print(f"\n{'='*70}")
    print(f"  {method_name} — Per-Intent Classification Report")
    print(f"{'='*70}")
    y_true = [r["true_intent"]      for r in results]
    y_pred = [r["predicted_intent"] for r in results]
    print(classification_report(y_true, y_pred, zero_division=0))

    # Per-category breakdown
    categories = sorted({r["category"] for r in results})
    print(f"\n  {method_name} — Per-Category Accuracy")
    print(f"  {'Category':<25} {'N':>5}  {'Intent Acc':>10}  {'Entity Acc':>10}")
    print(f"  {'-'*55}")
    for cat in categories:
        cat_rows = [r for r in results if r["category"] == cat]
        i_acc = _accuracy(cat_rows)
        e_acc = _entity_accuracy(cat_rows)
        print(f"  {cat:<25} {len(cat_rows):>5}  {i_acc:>9.1f}%  {e_acc:>9.1f}%")

    # Per-phrasing-style breakdown
    styles = sorted({r["phrasing_style"] for r in results})
    print(f"\n  {method_name} — Per-Phrasing-Style Accuracy")
    print(f"  {'Style':<25} {'N':>5}  {'Intent Acc':>10}")
    print(f"  {'-'*45}")
    for style in styles:
        s_rows = [r for r in results if r["phrasing_style"] == style]
        print(f"  {style:<25} {len(s_rows):>5}  {_accuracy(s_rows):>9.1f}%")


def print_comparison_table(
    v1: list[dict],
    v2: list[dict],
    v2_threshold: float,
) -> None:
    """Print a research-ready side-by-side comparison summary."""
    v1_lat = _latency_percentiles(v1)
    v2_lat = _latency_percentiles(v2)

    v1_ia  = _accuracy(v1)
    v2_ia  = _accuracy(v2)
    v1_ea  = _entity_accuracy(v1)
    v2_ea  = _entity_accuracy(v2)

    W = 72
    sep  = "+" + "-"*W + "+"
    hdr  = lambda s: f"| {s:^{W-2}} |"
    row  = lambda l, v1v, v2v: f"| {l:<28} | {v1v:>18} | {v2v:>18} |"

    print(f"\n{sep}")
    print(hdr("MANTRA AI — V1 vs V2 Benchmark Comparison"))
    print(sep)
    print(f"| {'Metric':<28} | {'V1 (Keyword Scan)':>18} | {'V2 (Sentence-BERT)':>18} |")
    print(sep)
    print(row("Test cases",            str(len(v1)),           str(len(v2))))
    print(row("V2 cosine threshold",   "—",                    str(v2_threshold)))
    print(sep)
    print(row("Intent accuracy (%)",   f"{v1_ia:.2f}",         f"{v2_ia:.2f}"))
    print(row("Entity accuracy (%)",   f"{v1_ea:.2f}",         f"{v2_ea:.2f}"))
    print(sep)
    print(row("Latency p50 (ms)",      f"{v1_lat['p50']:.2f}", f"{v2_lat['p50']:.2f}"))
    print(row("Latency p95 (ms)",      f"{v1_lat['p95']:.2f}", f"{v2_lat['p95']:.2f}"))
    print(row("Latency max (ms)",      f"{v1_lat['max']:.2f}", f"{v2_lat['max']:.2f}"))
    print(row("Latency mean (ms)",     f"{v1_lat['mean']:.2f}",f"{v2_lat['mean']:.2f}"))
    print(sep)
    delta_i = v2_ia - v1_ia
    delta_e = v2_ea - v1_ea
    sign_i  = "+" if delta_i >= 0 else ""
    sign_e  = "+" if delta_e >= 0 else ""
    print(row("Delta intent acc",      "baseline",             f"{sign_i}{delta_i:.2f}%"))
    print(row("Delta entity acc",      "baseline",             f"{sign_e}{delta_e:.2f}%"))
    print(sep)
    print()


# ---------------------------------------------------------------------------
# Results CSV writer
# ---------------------------------------------------------------------------

def save_results(
    v1: list[dict],
    v2: list[dict],
    output_path: Path,
) -> None:
    """Save per-row detailed results to a CSV with method column."""
    fieldnames = [
        "method", "utterance", "category", "phrasing_style",
        "true_intent", "true_entity",
        "predicted_intent", "predicted_entity",
        "correct_intent", "correct_entity",
        "latency_ms",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in v1:
            writer.writerow({"method": "V1", **r})
        for r in v2:
            writer.writerow({"method": "V2", **r})
    print(f"[benchmark] Detailed results saved to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="benchmark.py",
        description=(
            "Mantra AI V2 Evaluation Framework — "
            "compare V1 keyword scanning vs V2 sentence-transformers."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--csv", "-c",
        required=True,
        metavar="PATH",
        type=Path,
        help="Path to input CSV (utterance, true_intent, true_entity, category, phrasing_style)",
    )
    p.add_argument(
        "--output", "-o",
        default=Path("evaluation/results.csv"),
        metavar="PATH",
        type=Path,
        help="Path to save detailed results CSV (default: results.csv)",
    )
    p.add_argument(
        "--v2-threshold",
        default=0.40,
        type=float,
        metavar="FLOAT",
        dest="v2_threshold",
        help="Cosine similarity threshold for V2 (default: 0.40)",
    )
    p.add_argument(
        "--skip-v2",
        action="store_true",
        dest="skip_v2",
        help="Run only V1 (useful when sentence-transformers is not available)",
    )
    return p


def main() -> None:
    args = build_parser().parse_args()

    # ── Load data ─────────────────────────────────────────────────────────────
    rows = load_csv(args.csv)

    if args.skip_v2:
        # V1-only mode
        from sklearn.metrics import classification_report
        v1_results: list[dict] = []
        for row in rows:
            utt = row["utterance"]
            t0  = time.perf_counter()
            vi  = _v1_predict_intent(utt)
            ve  = _v1_predict_entity(utt)
            lat = (time.perf_counter() - t0) * 1000.0
            v1_results.append({
                "utterance":        utt,
                "category":         row["category"],
                "phrasing_style":   row["phrasing_style"],
                "true_intent":      row["true_intent"],
                "true_entity":      row["true_entity"],
                "predicted_intent": vi,
                "predicted_entity": ve,
                "correct_intent":   vi == row["true_intent"],
                "correct_entity":   _entity_match(ve, row["true_entity"]),
                "latency_ms":       round(lat, 4),
            })
        compute_metrics(v1_results, "V1 (Keyword Scan)")
        lat = _latency_percentiles(v1_results)
        print(f"\nV1 Latency  p50={lat['p50']}ms  p95={lat['p95']}ms  max={lat['max']}ms")
        save_results(v1_results, [], args.output)
        return

    # ── Full V1 + V2 evaluation ───────────────────────────────────────────────
    v1_results, v2_results = run_evaluation(rows, args.v2_threshold)

    # ── Metrics ───────────────────────────────────────────────────────────────
    compute_metrics(v1_results, "V1 (Keyword Scan)")
    compute_metrics(v2_results, f"V2 (Sentence-BERT, threshold={args.v2_threshold})")

    # ── Comparison table ──────────────────────────────────────────────────────
    print_comparison_table(v1_results, v2_results, args.v2_threshold)

    # ── Save results ──────────────────────────────────────────────────────────
    save_results(v1_results, v2_results, args.output)


if __name__ == "__main__":
    main()
