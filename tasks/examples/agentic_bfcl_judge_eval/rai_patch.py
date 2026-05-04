"""
Adds required NeurIPS 2026 E&D Track Responsible AI (RAI) metadata
to the HuggingFace-generated Croissant file for AgentJudgeBench.

Usage:
    python rai_patch.py                          # reads croissant.json, writes croissant_with_rai.json
    python rai_patch.py --in foo.json --out bar.json
"""

import json, argparse, pathlib

RAI_FIELDS = {
    # ── Responsible AI ────────────────────────────────────────────────────────
    "rai:hasSyntheticData": True,

    "rai:dataLimitations": (
        "AgentJudgeBench is entirely pipeline-generated synthetic data spanning 15 enterprise "
        "domains. No real-world agentic execution traces have been included or validated at "
        "submission time; generalization to production tool-call distributions is an open "
        "question. "
        "The programmatic scorer measures structural correctness (argument keys, ordering) but "
        "not semantic equivalence (e.g., argument-equivalent JSON with different key names); "
        "parameter-structure is the metric most affected by this gap (82.5 % human agreement "
        "vs. 97–98 % for other metrics). "
        "The easy→medium difficulty rewrite is unanimously validated as a strict hardening on "
        "only 58.1 % of records; a subset of medium records are better characterized as "
        "paraphrases rather than genuine difficulty increases. "
        "Judge configuration results (temperature, prompt format, CoT) are each validated on a "
        "single (judge, generator) test-bed pair and should be treated as suggestive rather "
        "than definitive for other pairings. "
        "This dataset is NOT recommended for: training generator models (it is designed for "
        "judge evaluation, not generation); evaluating non-tool-calling NLP tasks; or as a "
        "sole measure of real-world agentic reliability without validation on real traces."
    ),

    "rai:dataBiases": (
        "Topology distribution is intentionally imbalanced to mirror enterprise prevalence "
        "(fan-in 27.5 %, loop-like 5.9 %); unweighted aggregate figures shift by ≤1.5 pp "
        "under count-weighted averaging. "
        "All 15 seed domains are enterprise-oriented (e.g., IT Service Management, Contract "
        "Lifecycle Management, Energy Grid Operations); consumer, scientific, or public-sector "
        "workflows are not represented. "
        "The programmatic quality gate is entirely rule-based; no human labelers were involved "
        "in record creation, which may introduce systematic blind spots in naturalness or "
        "semantic plausibility. "
        "The 120-record human annotation study used to validate the programmatic scorer was "
        "conducted on hard-difficulty records only and may not fully characterize scorer "
        "behavior on easy/medium records. "
        "Generator and judge model selection reflects availability as of April 2026; results "
        "may not generalize to model families not included in the evaluation."
    ),

    "rai:personalSensitiveInformation": (
        "None. All records are fully synthetic and do not contain personally identifiable "
        "information (PII), health data, financial account details, or any other sensitive "
        "personal information. Domain labels and scenario descriptions are generic enterprise "
        "archetypes (e.g., 'IT incident ticket', 'contract clause') without reference to real "
        "organizations, individuals, or events."
    ),

    "rai:dataUseCases": (
        "Established use cases: "
        "(1) Benchmarking LLM judges for agentic tool-calling evaluation — measuring alignment "
        "of LLM judge verdicts with a deterministic programmatic reference across difficulty "
        "tiers, DAG topologies, and ground-truth availability conditions. "
        "(2) Selecting judge configurations for deployment — the dataset supports controlled "
        "comparison of judge models, prompt formats, and reference conditions. "
        "(3) Studying failure modes of LLM-as-judge systems on structured tasks — per-metric "
        "decomposition enables diagnosis of where judges fail (tool selection vs. parameter "
        "structure vs. sequence accuracy vs. coverage). "
        "Not established: "
        "Training generator models; evaluating semantic correctness beyond structural matching; "
        "measuring judge reliability on real agentic trajectories without additional validation."
    ),

    "rai:dataSocialImpact": (
        "Positive impacts: "
        "Enables practitioners to select LLM judges with principled, evidence-based criteria "
        "rather than ad hoc choices, reducing evaluation errors in agentic AI deployments. "
        "Surfaces failure modes (over-anchoring, no-GT ceiling, prompt-format sensitivity) "
        "that, once known, can be mitigated in evaluation pipeline design. "
        "Provides a reproducible benchmark that can track progress in LLM judge quality over "
        "time as new models are released. "
        "Negative risks and mitigations: "
        "Knowledge of judge failure modes could be exploited to craft outputs that score highly "
        "under specific judges without genuine quality improvement ('judge gaming'). Mitigation: "
        "the programmatic scorer is released alongside the LLM judges, providing an "
        "independent, non-gameable reference. "
        "Synthetic enterprise data may reinforce narrow framings of 'correct' tool use aligned "
        "with the 15 seed domains; practitioners should validate coverage for their specific "
        "deployment context. "
        "The convergence ceiling finding (77–82 % hard no-GT) may be misread as endorsing "
        "judge-free evaluation; the paper explicitly documents when judges are and are not "
        "reliable and recommends programmatic evaluation as a complement, not a replacement."
    ),

    # ── Provenance ────────────────────────────────────────────────────────────
    "prov:wasDerivedFrom": [
        {
            "@type": "sc:Dataset",
            "name": "Berkeley Function Calling Leaderboard (BFCL)",
            "url": "https://gorilla.cs.berkeley.edu/leaderboard.html",
            "description": (
                "AgentJudgeBench adopts the BFCL JSON schema for tool definitions and "
                "function-call records, extending it to multi-step DAG-structured workflows "
                "at three controlled difficulty tiers."
            )
        }
    ],

    "prov:wasGeneratedBy": {
        "@type": "prov:Activity",
        "prov:label": "AgentJudgeBench synthetic data pipeline",
        "description": (
            "Records were generated by a multi-stage LLM pipeline operating on enterprise "
            "domain seed labels. "
            "Stage 1 — Record construction: given an enterprise domain label, an LLM generates "
            "a use-case scenario, a typed tool inventory (JSON schema with constrained return "
            "types), executable pseudocode linking tool dependencies, a natural-language user "
            "utterance, and an ordered ground-truth execution trace. "
            "Stage 2 — Difficulty rewriting: each base record is rewritten into three "
            "difficulty variants (easy / medium / hard) by increasing query ambiguity while "
            "holding the ground-truth tool-call sequence constant. "
            "Stage 3 — Programmatic quality gate: every record passes (a) JSON-schema "
            "validation, argument-type verification, and trace consistency checks; and "
            "(b) programmatic argument-sufficiency, grounding-alignment, and naturalness "
            "checks. Records below threshold are rejected and regenerated. No LLM from the "
            "evaluation judge set (J) or any other model is involved in pre-filtering, "
            "eliminating self-reinforcing bias. "
            "Stage 4 — Human validation: a stratified 120-record annotation study (20 per "
            "DAG topology, hard difficulty) confirms 92.7 % overall metric-level agreement "
            "between the programmatic scorer and independent human annotators. "
            "All generation was performed with large language models accessed via API (models "
            "detailed in the accompanying paper, Appendix A). "
            "Dataset seed domains: IT Service Management, Contract Lifecycle Management, "
            "Energy Grid Operations, and 12 additional enterprise domains (full list in "
            "Appendix B of the paper)."
        )
    }
}


def patch(in_path: str, out_path: str) -> None:
    data = json.loads(pathlib.Path(in_path).read_text())

    # HF Croissant files may have the dataset object at the top level or inside @graph
    target = data
    if "@graph" in data:
        # find the sc:Dataset node
        for node in data["@graph"]:
            if node.get("@type") in ("sc:Dataset", "Dataset"):
                target = node
                break

    # Ensure @context declares the rai: and prov: prefixes
    ctx = target.get("@context", {})
    if isinstance(ctx, dict):
        ctx.setdefault("rai",  "https://mlcommons.org/croissant/RAI/")
        ctx.setdefault("prov", "http://www.w3.org/ns/prov#")
        target["@context"] = ctx
    elif isinstance(ctx, list):
        # context is a list of strings/dicts; append the prefix dict if missing
        prefixes = {"rai": "https://mlcommons.org/croissant/RAI/",
                    "prov": "http://www.w3.org/ns/prov#"}
        has_rai = any(isinstance(c, dict) and "rai" in c for c in ctx)
        if not has_rai:
            ctx.append(prefixes)

    for key, value in RAI_FIELDS.items():
        target[key] = value

    pathlib.Path(out_path).write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"Written to {out_path}")
    print(f"RAI fields added: {list(RAI_FIELDS.keys())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--in",  dest="src", default="croissant.json")
    parser.add_argument("--out", dest="dst", default="croissant_with_rai.json")
    args = parser.parse_args()
    patch(args.src, args.dst)
