#!/usr/bin/env python3
"""
Zero-cost analysis: computes Z1-Z10 from existing raw output files.
Run from the agentic_bfcl_judge_eval directory.
"""
import json, glob, re, os, csv, random
from collections import defaultdict
from math import sqrt

BASE = os.path.dirname(os.path.abspath(__file__))
ANNOTATION_CSV = os.path.expanduser("~/Downloads/agentjudgebench_annotations.csv")

GENERATORS = ["llama_3_3_70b_instruct", "llama_3_1_8b_instruct", "qwen3_32b", "smollm3_3b"]
JUDGES     = ["gpt_5_4", "claude_large", "reranker_gemini", "qwq_32b", "gpt_oss_20b", "gpt_oss_120b"]
DIFFS      = ["easy", "medium", "hard"]
METRICS    = ["tool_selection_accuracy", "parameter_structure_accuracy",
              "sequence_accuracy", "query_coverage_accuracy"]
METRIC_SHORT = {"tool_selection_accuracy": "tool",
                "parameter_structure_accuracy": "param",
                "sequence_accuracy": "seq",
                "query_coverage_accuracy": "cov"}

# ─── helpers ────────────────────────────────────────────────────────────────

def find_file(gen, judge, diff):
    pattern = os.path.join(BASE, gen, f"judged_by_{judge}",
                           f"judge_{gen}_{judge}_{diff}_output_*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    return sorted(files)[-1]   # most recent

def load_records(gen, judge, diff):
    path = find_file(gen, judge, diff)
    if not path:
        return []
    with open(path) as f:
        return json.load(f)

def get_metric_scores(record, no_gt=False):
    key = "per_metric_comparison_no_gt" if no_gt else "per_metric_comparison"
    d = record.get(key) or {}
    scores = {}
    for m in METRICS:
        entry = d.get(m)
        if entry:
            scores[m] = {"prog": entry.get("programmatic_accuracy"),
                         "llm":  entry.get("llm_accuracy"),
                         "match": entry.get("match_score")}
    return scores

def align(record, no_gt=False):
    """Mean match_score across 4 metrics (= alignment %)."""
    s = get_metric_scores(record, no_gt)
    vals = [v["match"] for v in s.values() if v["match"] is not None]
    return (sum(vals) / len(vals) * 100) if vals else None

# ─── Z9: exact record count ─────────────────────────────────────────────────

print("=" * 70)
print("Z9 — EXACT RECORD COUNTS")
print("=" * 70)
for diff in DIFFS:
    path = os.path.join(BASE, f"input_{diff}.jsonl")
    with open(path) as f:
        n = sum(1 for _ in f)
    print(f"  {diff}: {n} records")

# Verify via one output file
recs = load_records("llama_3_1_8b_instruct", "gpt_5_4", "easy")
print(f"  Verification (llama_3_1_8b/gpt_5_4/easy output): {len(recs)} records")
recs70 = load_records("llama_3_3_70b_instruct", "gpt_5_4", "easy")
print(f"  Verification (llama_3_3_70b/gpt_5_4/easy output): {len(recs70)} records")

# ─── load entire corpus into memory ─────────────────────────────────────────

print("\nLoading all 72 core files …", flush=True)
DATA = {}  # (gen, judge, diff) -> list of records
for gen in GENERATORS:
    for judge in JUDGES:
        for diff in DIFFS:
            recs = load_records(gen, judge, diff)
            if recs:
                DATA[(gen, judge, diff)] = recs
print(f"  Loaded {len(DATA)} cells, {sum(len(v) for v in DATA.values())} total records")

# ─── Z1: per-metric alignment GT vs no-GT by judge × difficulty ─────────────

print("\n" + "=" * 70)
print("Z1 — PER-METRIC ALIGNMENT WITH-GT vs NO-GT (averaged over generators)")
print("=" * 70)

# judge_diff_metric -> list of (gt_match, nogt_match)
jdm = defaultdict(list)
for (gen, judge, diff), recs in DATA.items():
    for r in recs:
        sg = get_metric_scores(r, no_gt=False)
        sn = get_metric_scores(r, no_gt=True)
        for m in METRICS:
            if m in sg and m in sn:
                gv = sg[m]["match"]
                nv = sn[m]["match"]
                if gv is not None and nv is not None:
                    jdm[(judge, diff, m)].append((gv, nv))

print(f"\n{'Judge':<20} {'Diff':<8} {'Metric':<8} {'GT%':>7} {'NoGT%':>7} {'Lift':>7}")
for judge in JUDGES:
    for diff in DIFFS:
        for m in METRICS:
            pairs = jdm[(judge, diff, m)]
            if not pairs:
                continue
            gt_mean  = sum(p[0] for p in pairs) / len(pairs) * 100
            ngt_mean = sum(p[1] for p in pairs) / len(pairs) * 100
            lift = gt_mean - ngt_mean
            print(f"  {judge:<20} {diff:<8} {METRIC_SHORT[m]:<8} {gt_mean:7.2f} {ngt_mean:7.2f} {lift:+7.2f}")

# Summary table: judge × metric (aggregated over difficulty) for over-anchors
print("\n--- Over-anchoring judges (GT lift < 0) per metric (all difficulties) ---")
print(f"{'Judge':<20} {'tool':>7} {'param':>7} {'seq':>7} {'cov':>7}")
for judge in ["gpt_5_4", "reranker_gemini"]:
    row = []
    for m in METRICS:
        pairs = []
        for diff in DIFFS:
            pairs.extend(jdm[(judge, diff, m)])
        lift = (sum(p[0]-p[1] for p in pairs) / len(pairs) * 100) if pairs else 0
        row.append(f"{lift:+7.2f}")
    print(f"  {judge:<20} {'  '.join(row)}")

# ─── Z2: over-anchoring case studies ────────────────────────────────────────

print("\n" + "=" * 70)
print("Z2 — OVER-ANCHORING CASE STUDIES (Gemini, hard, prog<1 & GT=1 & noGT<1)")
print("=" * 70)

cases = []
for gen in GENERATORS:
    key = (gen, "reranker_gemini", "hard")
    recs = DATA.get(key, [])
    for r in recs:
        sg = get_metric_scores(r, no_gt=False)
        sn = get_metric_scores(r, no_gt=True)
        for m in METRICS:
            if m not in sg or m not in sn:
                continue
            pg = sg[m]["prog"]
            lg = sg[m]["llm"]
            ln = sn[m]["llm"]
            if pg is not None and lg is not None and ln is not None:
                if pg < 1.0 and lg == 1.0 and ln < lg:
                    cases.append({
                        "gen": gen, "id": r.get("id"), "dag": r.get("dag_type"),
                        "metric": METRIC_SHORT[m],
                        "prog": pg, "llm_gt": lg, "llm_ngt": ln,
                        "query": (r.get("user_message") or "")[:200]
                    })

print(f"  Found {len(cases)} over-anchoring instances (Gemini, hard)")
for c in cases[:5]:
    print(f"\n  ID: {c['id']}  DAG: {c['dag']}  Metric: {c['metric']}")
    print(f"  Prog={c['prog']:.2f}  LLM_GT={c['llm_gt']:.2f}  LLM_noGT={c['llm_ngt']:.2f}")
    print(f"  Query: {c['query'][:180]} …")

# ─── Z4: inter-judge confusion matrices ─────────────────────────────────────

print("\n" + "=" * 70)
print("Z4 — INTER-JUDGE CONFUSION MATRICES (verdict level 0/0.5/1)")
print("=" * 70)

def discretize(v):
    if v is None: return None
    if v <= 0.1: return 0.0
    if v >= 0.9: return 1.0
    return 0.5

def confusion_matrix(j1, j2, no_gt=False):
    from collections import Counter
    counts = Counter()
    for gen in GENERATORS:
        for diff in DIFFS:
            r1_map = {r["id"]: r for r in DATA.get((gen, j1, diff), [])}
            r2_map = {r["id"]: r for r in DATA.get((gen, j2, diff), [])}
            common_ids = set(r1_map) & set(r2_map)
            for rid in common_ids:
                s1 = get_metric_scores(r1_map[rid], no_gt)
                s2 = get_metric_scores(r2_map[rid], no_gt)
                for m in METRICS:
                    if m in s1 and m in s2:
                        v1 = discretize(s1[m]["llm"])
                        v2 = discretize(s2[m]["llm"])
                        if v1 is not None and v2 is not None:
                            counts[(v1, v2)] += 1
    return counts

def cohen_kappa(cm):
    total = sum(cm.values())
    if total == 0: return 0.0
    labels = [0.0, 0.5, 1.0]
    po = sum(cm[(v, v)] for v in labels) / total
    pe = 0.0
    for v in labels:
        row_sum = sum(cm[(v, w)] for w in labels)
        col_sum = sum(cm[(w, v)] for w in labels)
        pe += (row_sum / total) * (col_sum / total)
    return (po - pe) / (1 - pe) if pe < 1 else 0.0

pairs_to_check = [
    ("qwq_32b",      "gpt_oss_120b"),
    ("claude_large", "gpt_oss_20b"),
    ("gpt_5_4",      "reranker_gemini"),
    ("gpt_5_4",      "qwq_32b"),
]

for cond, no_gt in [("with-GT", False), ("no-GT", True)]:
    print(f"\n  Condition: {cond}")
    print(f"  {'Pair':<35} {'κ':>8}  {'P(agree)':>10}")
    for j1, j2 in pairs_to_check:
        cm = confusion_matrix(j1, j2, no_gt)
        kappa = cohen_kappa(cm)
        total = sum(cm.values())
        agree = sum(cm[(v, v)] for v in [0.0, 0.5, 1.0])
        pa = agree / total if total else 0
        print(f"  {j1} × {j2:<20} {kappa:8.3f}  {pa:10.3f}  (N={total})")

# ─── Z5: capacity-rank × kappa Spearman ─────────────────────────────────────

print("\n" + "=" * 70)
print("Z5 — SPEARMAN CORR(capacity_rank_diff, pairwise_κ)")
print("=" * 70)

# capacity rank (1=strongest): GPT-5.4=1, Claude=2, Gemini=3, QwQ=4, 120B=5, 20B=6
cap_rank = {"gpt_5_4": 1, "claude_large": 2, "reranker_gemini": 3,
            "qwq_32b": 4, "gpt_oss_120b": 5, "gpt_oss_20b": 6}

all_pairs = [(JUDGES[i], JUDGES[j]) for i in range(len(JUDGES)) for j in range(i+1, len(JUDGES))]

for cond, no_gt in [("with-GT", False), ("no-GT", True)]:
    rank_diffs, kappas = [], []
    print(f"\n  Condition: {cond}")
    print(f"  {'Pair':<35} {'|Δrank|':>8} {'κ':>8}")
    for j1, j2 in all_pairs:
        cm = confusion_matrix(j1, j2, no_gt)
        k = cohen_kappa(cm)
        rd = abs(cap_rank[j1] - cap_rank[j2])
        rank_diffs.append(rd)
        kappas.append(k)
        print(f"  {j1} × {j2:<20} {rd:8d} {k:8.3f}")
    # spearman
    n = len(rank_diffs)
    def rank_vec(v):
        sorted_v = sorted(range(n), key=lambda i: v[i])
        ranks = [0]*n
        for rank, idx in enumerate(sorted_v):
            ranks[idx] = rank
        return ranks
    r1 = rank_vec(rank_diffs)
    r2 = rank_vec(kappas)
    d2 = sum((r1[i]-r2[i])**2 for i in range(n))
    rho = 1 - 6*d2/(n*(n**2-1))
    print(f"\n  Spearman rho = {rho:.3f} (N={n} pairs)")

# ─── Z6: jury-of-judges alignment ────────────────────────────────────────────

print("\n" + "=" * 70)
print("Z6 — JURY-OF-JUDGES ALIGNMENT (soft mean ensemble vs programmatic)")
print("=" * 70)

def jury_alignment(no_gt=False):
    """Per-record: mean of 6 judges' llm_accuracy, then compare to prog."""
    results = defaultdict(list)  # diff -> list of jury match scores
    for gen in GENERATORS:
        for diff in DIFFS:
            # build id->per-judge llm scores
            id_to_scores = defaultdict(dict)  # id -> {judge -> {metric -> llm}}
            for judge in JUDGES:
                recs = DATA.get((gen, judge, diff), [])
                for r in recs:
                    rid = r["id"]
                    s = get_metric_scores(r, no_gt)
                    id_to_scores[rid][judge] = s
            # compute jury alignment for each record
            for rid, judge_scores in id_to_scores.items():
                # need all 6 judges
                if len(judge_scores) < 6:
                    continue
                # get prog scores from any judge (they should be same)
                ref_judge = JUDGES[0]
                ref_scores = get_metric_scores(
                    next(r for r in DATA.get((gen, ref_judge, diff), []) if r["id"] == rid),
                    no_gt=False  # prog is same regardless
                )
                metric_matches = []
                for m in METRICS:
                    llm_vals = [judge_scores[j].get(m, {}).get("llm")
                                for j in JUDGES if judge_scores.get(j, {}).get(m) is not None
                                and judge_scores[j][m].get("llm") is not None]
                    if not llm_vals:
                        continue
                    jury_score = sum(llm_vals) / len(llm_vals)
                    prog_score = ref_scores.get(m, {}).get("prog")
                    if prog_score is None:
                        continue
                    match = 1.0 - abs(jury_score - prog_score)
                    metric_matches.append(match)
                if metric_matches:
                    results[diff].append(sum(metric_matches)/len(metric_matches)*100)
    return results

for cond, no_gt in [("with-GT", False), ("no-GT", True)]:
    res = jury_alignment(no_gt)
    print(f"\n  Jury ({cond}):")
    for diff in DIFFS:
        vals = res[diff]
        if vals:
            m = sum(vals)/len(vals)
            # 95% CI via bootstrap (1000 iters)
            random.seed(42)
            means_b = [sum(random.choices(vals, k=len(vals)))/len(vals) for _ in range(1000)]
            lo, hi = sorted(means_b)[25], sorted(means_b)[974]
            print(f"    {diff:8s}: {m:.2f}%  95% CI [{lo:.2f}, {hi:.2f}]  (N={len(vals)})")

# ─── Z7: bootstrap CIs per judge (averaged over generators) ─────────────────

print("\n" + "=" * 70)
print("Z7 — BOOTSTRAP 95% CIs PER JUDGE × DIFFICULTY")
print("=" * 70)

random.seed(42)
def bootstrap_ci(vals, n_boot=2000):
    if not vals: return (None, None)
    means = [sum(random.choices(vals, k=len(vals)))/len(vals) for _ in range(n_boot)]
    return sorted(means)[int(0.025*n_boot)], sorted(means)[int(0.975*n_boot)]

print(f"\n  {'Judge':<20} {'Diff':<8} {'GT%':>7} {'[lo,hi]':>16}  {'NoGT%':>7} {'[lo,hi]':>16}")
for judge in JUDGES:
    for diff in DIFFS:
        gt_vals, ngt_vals = [], []
        for gen in GENERATORS:
            for r in DATA.get((gen, judge, diff), []):
                av = align(r, no_gt=False)
                an = align(r, no_gt=True)
                if av is not None: gt_vals.append(av)
                if an is not None: ngt_vals.append(an)
        gt_m  = sum(gt_vals)/len(gt_vals) if gt_vals else 0
        ngt_m = sum(ngt_vals)/len(ngt_vals) if ngt_vals else 0
        lo_g, hi_g = bootstrap_ci(gt_vals)
        lo_n, hi_n = bootstrap_ci(ngt_vals)
        print(f"  {judge:<20} {diff:<8} {gt_m:7.2f} [{lo_g:.2f},{hi_g:.2f}]  {ngt_m:7.2f} [{lo_n:.2f},{hi_n:.2f}]")

# ─── Z8: human vs judge alignment (120 annotated records) ────────────────────

print("\n" + "=" * 70)
print("Z8 — JUDGE ALIGNMENT AGAINST HUMAN ANNOTATIONS (hard, 120 records)")
print("=" * 70)

annot = []
with open(ANNOTATION_CSV) as f:
    for row in csv.DictReader(f):
        annot.append(row)

annot_by_id = {r["id"]: r for r in annot}
print(f"  Annotation records: {len(annot_by_id)}")

METRIC_COLS = {
    "tool_selection_accuracy": ("prog_tool", "agree_tool"),
    "parameter_structure_accuracy": ("prog_param", "agree_param"),
    "sequence_accuracy": ("prog_seq", "agree_seq"),
    "query_coverage_accuracy": ("prog_cov", "agree_cov"),
}

def human_score(annot_row, metric):
    """
    Returns what the human believes the correct score is.
    If agree=1, human agrees with programmatic -> human_score = prog_score.
    If agree=0, human disagrees with programmatic -> flip binary:
      if prog > 0.5: human says ~0  (judge gave credit, human says no)
      if prog <= 0.5: human says ~1 (judge denied credit, human says yes)
    """
    prog_col, agree_col = METRIC_COLS[metric]
    try:
        prog = float(annot_row[prog_col])
        agree = int(annot_row[agree_col])
    except (ValueError, KeyError):
        return None
    if agree == 1:
        return prog
    else:
        return 0.0 if prog >= 0.5 else 1.0

print(f"\n  {'Judge':<20} {'GT-vs-Prog%':>13} {'GT-vs-Human%':>14} {'∆(Human-Prog)':>14}")
for judge in JUDGES:
    # use llama_3_3_70b_instruct as reference generator (largest)
    recs_hard = {r["id"]: r for r in DATA.get(("llama_3_3_70b_instruct", judge, "hard"), [])}
    # also llama_3_1_8b if 70b missing
    recs_hard2 = {r["id"]: r for r in DATA.get(("llama_3_1_8b_instruct", judge, "hard"), [])}

    prog_aligns, human_aligns = [], []
    for ann_id, ann_row in annot_by_id.items():
        rec = recs_hard.get(ann_id) or recs_hard2.get(ann_id)
        if rec is None:
            continue
        sg = get_metric_scores(rec, no_gt=False)
        pm_vals, hm_vals = [], []
        for m in METRICS:
            if m not in sg: continue
            llm = sg[m]["llm"]
            prog = sg[m]["prog"]
            hs = human_score(ann_row, m)
            if llm is None or prog is None or hs is None: continue
            pm_vals.append(1.0 - abs(llm - prog))
            hm_vals.append(1.0 - abs(llm - hs))
        if pm_vals:
            prog_aligns.append(sum(pm_vals)/len(pm_vals)*100)
            human_aligns.append(sum(hm_vals)/len(hm_vals)*100)

    if prog_aligns:
        pa = sum(prog_aligns)/len(prog_aligns)
        ha = sum(human_aligns)/len(human_aligns)
        print(f"  {judge:<20} {pa:13.2f} {ha:14.2f} {ha-pa:+14.2f}  (N={len(prog_aligns)})")
    else:
        print(f"  {judge:<20} — no matching records —")

# ─── Z10: sensitivity analysis on metric weighting ───────────────────────────

print("\n" + "=" * 70)
print("Z10 — SENSITIVITY: ALIGNMENT UNDER ALTERNATIVE METRIC WEIGHTS")
print("=" * 70)

WEIGHT_SCHEMES = {
    "Equal (default)":       [1, 1, 1, 1],
    "Seq×2":                 [1, 1, 2, 1],
    "Param×2":               [1, 2, 1, 1],
    "Cov×0.5":               [1, 1, 1, 0.5],
    "Seq×2 + Param×2":       [1, 2, 2, 1],
}

def weighted_align(record, weights, no_gt=False):
    s = get_metric_scores(record, no_gt)
    total_w, total_wm = 0.0, 0.0
    for m, w in zip(METRICS, weights):
        if m in s and s[m]["match"] is not None:
            total_wm += w * s[m]["match"]
            total_w  += w
    return (total_wm / total_w * 100) if total_w > 0 else None

print(f"\n  Judge alignment (with-GT, averaged over all generators + difficulties)")
print(f"  {'Judge':<20}", end="")
for scheme_name in WEIGHT_SCHEMES:
    print(f"  {scheme_name[:14]:>14}", end="")
print()

for judge in JUDGES:
    print(f"  {judge:<20}", end="")
    for scheme_name, weights in WEIGHT_SCHEMES.items():
        vals = []
        for gen in GENERATORS:
            for diff in DIFFS:
                for r in DATA.get((gen, judge, diff), []):
                    v = weighted_align(r, weights, no_gt=False)
                    if v is not None:
                        vals.append(v)
        m = sum(vals)/len(vals) if vals else 0
        print(f"  {m:>14.2f}", end="")
    print()

print("\n  Ranking stability check (Spearman rho of Equal vs Seq×2 and Equal vs Param×2):")
def judge_rank_under_scheme(weights, no_gt=False):
    scores = {}
    for judge in JUDGES:
        vals = []
        for gen in GENERATORS:
            for diff in DIFFS:
                for r in DATA.get((gen, judge, diff), []):
                    v = weighted_align(r, weights, no_gt)
                    if v is not None: vals.append(v)
        scores[judge] = sum(vals)/len(vals) if vals else 0
    return [scores[j] for j in JUDGES]

def spearman(a, b):
    n = len(a)
    def ranks(v):
        sv = sorted(range(n), key=lambda i: v[i])
        r = [0]*n
        for rank, idx in enumerate(sv): r[idx] = rank
        return r
    r1, r2 = ranks(a), ranks(b)
    d2 = sum((r1[i]-r2[i])**2 for i in range(n))
    return 1 - 6*d2/(n*(n**2-1))

base_scores = judge_rank_under_scheme([1,1,1,1])
for scheme_name, weights in list(WEIGHT_SCHEMES.items())[1:]:
    alt = judge_rank_under_scheme(weights)
    rho = spearman(base_scores, alt)
    print(f"    Equal vs {scheme_name}: rho = {rho:.4f}")

# ─── final summary ────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("DONE — see results above for LaTeX insertion")
print("=" * 70)
