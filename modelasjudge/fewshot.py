"""fewshot.py — few-shot exemplar selection and prompt rendering for free generation.

Two halves:

1. **Manifest.** For each benchmark question, which other questions serve as
   its worked examples. Built once per (benchmark, k, seed), saved as JSON and
   shared by every model, so model comparisons never depend on which exemplars
   a given model happened to draw. Selection rules:

   - same pool as the target: the reasoning_type, except that knowledge,
     inference and abstention share one pool ("world_qa");
   - in world_qa, one exemplar from each of the three types (the abstention
     exemplar always being an 'insufficient information' refusal), in random
     order, so no draw tilts the model toward or away from abstaining;
   - never the same source text (htids normalized), never the same author,
     never a near-duplicate prompt (Jaccard >= 0.6 over the first 20 words
     of main_question);
   - a shared 2048-token ceiling, counted with Talkie's tokenizer for every
     model: if target + exemplars + a projected answer window would exceed it,
     drop the last-sampled exemplar and log the fallback.

2. **Rendering.** The same items rendered three ways: chat messages (API and
   HF-instruct models), the literal Talkie-IT chat string, and one continuous
   completion document for base models. Every block carries its own LENGTH:
   line; the system prompt no longer carries the target's length spec.

With k = 0 the renderers produce the new format with no exemplars: the control
that separates "exemplars help" from "the new format helps".

CLI:
    python fewshot.py build BENCHMARK.jsonl --k 3 --seed 0
    python fewshot.py preview BENCHMARK.jsonl --k 3 --seed 0 --qnum 605 [--out DIR]
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import importlib.util
import json
import math
import os
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import free_generation as fg

SCRIPT_DIR = Path(__file__).resolve().parent
MANIFEST_DIR = SCRIPT_DIR / "fewshot_manifests"

RULES_VERSION = 1          # bump when selection rules change; recorded in every manifest
CEILING = 2048             # shared context ceiling, applied to every model
SAFETY_MARGIN = 64         # template overhead, special tokens, tokenizer drift
WINDOW_MULT = 1.5          # projected answer window = 1.5 x zero-shot max_tokens ...
WINDOW_MIN = 64            # ... but never less than this
STEM_WORDS = 20            # near-duplicate check: first N words of main_question
STEM_JACCARD = 0.6
DELIM = "* * *"            # exemplar separator in the completion format

POOL_OF = {"knowledge": "world_qa", "inference": "world_qa", "abstention": "world_qa"}
STRATA = {"world_qa": ("knowledge", "inference", "abstention")}
# 5/62 abstention questions are false-premise traps rather than refusals; an
# abstention exemplar exists to show the model that refusing is allowed.
ABSTENTION_EXEMPLAR_MUST_REFUSE = True

BASE_STOPS = ("\n" + DELIM, "\nCONTEXT:", "<|endoftext|>", "<|end|>", "<|user|>")

FEWSHOT_NOTE = (
    " The questions before the last are worked examples drawn from other books "
    "and periods: follow their form, but answer the final question from its own "
    "context."
)
SYSTEM_PROMPT_A_FS = (
    "You will be asked to answer a question in a way that fits the beliefs and "
    "expository style of a specific historical context. If the context described "
    "would not contain enough information to answer the question, respond simply "
    "'insufficient information.' Otherwise, answer at the length given with each "
    "question."
)
SYSTEM_PROMPT_B_FS = (
    "Answer the question in a way that fits the beliefs and expository style of "
    "the historical context described. As a rough guideline, answer at the length "
    "given with each question."
)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

def pool_key(q: dict) -> str:
    return POOL_OF.get(q["reasoning_type"], q["reasoning_type"])


def source_key(q: dict) -> str:
    """'hvd.hn1eg5', 'hn1eg5' and 'HN1EG5' all name the same book in 1.0."""
    return re.sub(r"^(hvd|uc1|mdp|nyp|uiug)\.", "", str(q.get("source_htid", "")).strip().lower())


def _stem(q: dict) -> set[str]:
    return set(re.sub(r"\W+", " ", q.get("main_question", "").lower()).split()[:STEM_WORDS])


def is_refusal(q: dict) -> bool:
    return "insufficient information" in q["answer_strings"][0].lower()


def eligible(target: dict, cand: dict) -> bool:
    if cand["question_number"] == target["question_number"]:
        return False
    if pool_key(cand) != pool_key(target):
        return False
    if source_key(cand) == source_key(target):
        return False
    author = (target.get("source_author") or "").strip()
    if author and (cand.get("source_author") or "").strip() == author:
        return False
    a, b = _stem(target), _stem(cand)
    if a and b and len(a & b) / len(a | b) >= STEM_JACCARD:
        return False
    return True


def _fits_stratum(q: dict, stratum: str) -> bool:
    if q["reasoning_type"] != stratum:
        return False
    if stratum == "abstention" and ABSTENTION_EXEMPLAR_MUST_REFUSE:
        return is_refusal(q)
    return True


def sample_exemplars(target: dict, questions: list[dict], k: int, rng: random.Random) -> tuple[list[int], int]:
    """Return (exemplar qnums in presentation order, number eligible)."""
    cands = [c for c in questions if eligible(target, c)]
    strata = STRATA.get(pool_key(target))
    if not strata:
        qnums = sorted(c["question_number"] for c in cands)
        return rng.sample(qnums, min(k, len(qnums))), len(qnums)
    # Stratified: one per stratum in shuffled order (cycling if k > #strata).
    order = list(strata)
    rng.shuffle(order)
    picks: list[int] = []
    for i in range(k):
        stratum = order[i % len(order)]
        avail = sorted(c["question_number"] for c in cands
                       if _fits_stratum(c, stratum) and c["question_number"] not in picks)
        if avail:
            picks.append(rng.choice(avail))
    return picks, len(cands)


# ---------------------------------------------------------------------------
# Item blocks and prompts
# ---------------------------------------------------------------------------

def target_frame(q: dict) -> str:
    return q.get("candidate_metadata_frame") or q.get("metadata_frame", "")


def item_block(q: dict, frame: str, answer: str | None = None) -> str:
    """CONTEXT / QUESTION / LENGTH / ANSWER block shared by all three formats."""
    _, spec = fg.make_length_spec(q.get("answer_strings", []), q.get("question_category", ""))
    s = f"CONTEXT: {frame}\nQUESTION: {q.get('main_question', '')}\nLENGTH: {spec}\nANSWER:"
    return s if answer is None else f"{s} {answer}"


def exemplar_answer(q: dict) -> str:
    return q["answer_strings"][0]


def system_prompt(target: dict, k: int) -> str:
    zero = fg._select_system_prompt(target.get("reasoning_type", ""), target.get("answer_strings", []))
    base = SYSTEM_PROMPT_A_FS if zero == fg.SYSTEM_PROMPT_A else SYSTEM_PROMPT_B_FS
    return base + (FEWSHOT_NOTE if k > 0 else "")


@dataclass
class FewShotPrompt:
    system: str
    turns: list[dict]           # alternating user/assistant, ending with the target user turn
    completion_text: str        # continuous document for base models, ends "ANSWER:"
    max_tokens: int             # answer cap: identical to the zero-shot cap
    length_spec: str
    exemplars: list[int]

    def chat_messages(self) -> list[dict]:
        return [{"role": "system", "content": self.system}] + self.turns

    def talkie_it_text(self) -> str:
        """Literal Talkie-IT string; mirrors talkie.chat.format_chat."""
        tag = {"system": "<|system|>", "user": "<|user|>", "assistant": "<|assistant|>"}
        return "".join(f"{tag[m['role']]}{m['content']}<|end|>" for m in self.chat_messages()) + "<|assistant|>"


def render(target: dict, exemplar_qs: list[dict]) -> FewShotPrompt:
    _, _, max_tokens, length_spec = fg.build_prompts(target)
    system = system_prompt(target, len(exemplar_qs))
    turns: list[dict] = []
    for e in exemplar_qs:
        turns.append({"role": "user", "content": item_block(e, e.get("metadata_frame", ""))})
        turns.append({"role": "assistant", "content": exemplar_answer(e)})
    turns.append({"role": "user", "content": item_block(target, target_frame(target))})
    parts = [system]
    parts += [item_block(e, e.get("metadata_frame", ""), exemplar_answer(e)) for e in exemplar_qs]
    parts.append(item_block(target, target_frame(target)))
    return FewShotPrompt(
        system=system, turns=turns,
        completion_text=f"\n\n{DELIM}\n\n".join(parts),
        max_tokens=max_tokens, length_spec=length_spec,
        exemplars=[e["question_number"] for e in exemplar_qs],
    )


def render_from_manifest(target: dict, manifest: dict, by_qnum: dict) -> tuple[FewShotPrompt, dict]:
    entry = manifest["entries"][str(target["question_number"])]
    return render(target, [by_qnum[n] for n in entry["exemplars"]]), entry


def truncate_at_stops(text: str, stops=BASE_STOPS) -> str:
    cut = min((i for i in (text.find(s) for s in stops) if i >= 0), default=-1)
    return text if cut < 0 else text[:cut]


# ---------------------------------------------------------------------------
# Reference tokenizer (Talkie's BPE), used only for the budget check
# ---------------------------------------------------------------------------

def _find_talkie_vocab() -> str | None:
    if os.environ.get("TALKIE_VOCAB"):
        return os.environ["TALKIE_VOCAB"]
    roots = [os.environ.get("HF_HOME", ""), str(Path.home() / ".cache" / "huggingface")]
    for root in filter(None, roots):
        for name in ("talkie-1930-13b-base", "talkie-1930-13b-it"):
            hits = glob.glob(os.path.join(root, "hub", f"models--talkie-lm--{name}", "snapshots", "*", "vocab.txt"))
            if hits:
                return hits[0]
    return None


def load_reference_tokenizer():
    """Return a token-counting function using Talkie's base vocab."""
    vocab = _find_talkie_vocab()
    if vocab is None:
        raise RuntimeError(
            "Building a few-shot manifest needs Talkie's vocab.txt (the shared reference "
            "tokenizer for the 2048-token budget). Set TALKIE_VOCAB, or run `talkie download`, "
            "or copy a prebuilt manifest into fewshot_manifests/."
        )
    try:
        from talkie.tokenizer import build_tokenizer
    except ImportError:
        path = SCRIPT_DIR.parent.parent / "talkie" / "src" / "talkie" / "tokenizer.py"
        if not path.exists():
            raise RuntimeError("talkie.tokenizer not importable and no sibling talkie/ checkout found.")
        spec = importlib.util.spec_from_file_location("_talkie_tokenizer", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        build_tokenizer = mod.build_tokenizer
    enc = build_tokenizer(vocab, "base")
    return lambda s: len(enc.encode(s, disallowed_special=()))


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def benchmark_sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest_path(benchmark_path, k: int, seed: int, sha: str | None = None) -> Path:
    # The public sample and the full file share version "1.0", so the hash is in the name.
    sha = sha or benchmark_sha256(benchmark_path)
    return MANIFEST_DIR / f"fewshot_manifest__{fg._benchmark_version(benchmark_path)}__{sha[:8]}__k{k}_s{seed}.json"


def projected_window(q: dict) -> int:
    _, _, max_tokens, _ = fg.build_prompts(q)
    return max(WINDOW_MIN, math.ceil(WINDOW_MULT * max_tokens))


def build_manifest(questions: list[dict], k: int, seed: int, ntok) -> dict:
    by_q = {q["question_number"]: q for q in questions}
    delim_tok = ntok(f"\n\n{DELIM}\n\n")
    entries = {}
    for t in questions:
        # Per-question RNG (str seeds hash deterministically): a question's
        # exemplars don't depend on file order or on -n subsetting.
        rng = random.Random(f"{seed}:{t['question_number']}")
        picks, n_eligible = sample_exemplars(t, questions, k, rng)
        fixed = (ntok(system_prompt(t, k)) + delim_tok + ntok(item_block(t, target_frame(t)))
                 + projected_window(t) + SAFETY_MARGIN)
        ex_tok = [ntok(item_block(by_q[p], by_q[p].get("metadata_frame", ""), exemplar_answer(by_q[p]))) + delim_tok
                  for p in picks]
        kk = len(picks)
        while kk > 0 and fixed + sum(ex_tok[:kk]) > CEILING:
            kk -= 1   # drop the last-sampled exemplar: no length bias in which ones survive
        entries[str(t["question_number"])] = {
            "reasoning_type": t["reasoning_type"],
            "pool": pool_key(t),
            "k": kk,
            "exemplars": picks[:kk],
            "exemplar_types": [by_q[p]["reasoning_type"] for p in picks[:kk]],
            "dropped": picks[kk:],
            "fallback": kk < len(picks),
            "short_pool": len(picks) < k,
            "n_eligible": n_eligible,
            "projected_tokens": fixed + sum(ex_tok[:kk]),
        }
    return {
        "rules_version": RULES_VERSION,
        "k_requested": k,
        "seed": seed,
        "ceiling": CEILING,
        "safety_margin": SAFETY_MARGIN,
        "window_mult": WINDOW_MULT,
        "window_min": WINDOW_MIN,
        "reference_tokenizer": "talkie-1930-13b base vocab",
        "pools": POOL_OF,
        "strata": {k_: list(v) for k_, v in STRATA.items()},
        "abstention_exemplar_must_refuse": ABSTENTION_EXEMPLAR_MUST_REFUSE,
        "entries": entries,
    }


def summarize(manifest: dict) -> str:
    E = list(manifest["entries"].values())
    kd = dict(sorted(Counter(e["k"] for e in E).items()))
    fb = [q for q, e in manifest["entries"].items() if e["fallback"]]
    sp = [q for q, e in manifest["entries"].items() if e["short_pool"]]
    lines = [f"few-shot manifest k={manifest['k_requested']} seed={manifest['seed']}: k distribution {kd}; "
             f"max projected tokens {max((e['projected_tokens'] for e in E), default=0)}/{manifest['ceiling']}"]
    if fb:
        lines.append(f"  FALLBACK (ceiling) on {len(fb)} questions: {fb[:20]}{' ...' if len(fb) > 20 else ''}")
    if sp:
        lines.append(f"  SHORT POOL (too few eligible exemplars) on {len(sp)} questions: {sp[:20]}")
    return "\n".join(lines)


def validate_manifest(manifest: dict, questions: list[dict], sha: str, k: int, seed: int, path) -> None:
    problems = []
    if manifest.get("benchmark_sha256") != sha:
        problems.append("benchmark SHA-256 differs (benchmark edited since the manifest was built)")
    if manifest.get("k_requested") != k or manifest.get("seed") != seed:
        problems.append(f"built for k={manifest.get('k_requested')} seed={manifest.get('seed')}, requested k={k} seed={seed}")
    if manifest.get("rules_version") != RULES_VERSION:
        problems.append(f"rules_version {manifest.get('rules_version')} != current {RULES_VERSION}")
    missing = [q["question_number"] for q in questions if str(q["question_number"]) not in manifest.get("entries", {})]
    if missing:
        problems.append(f"{len(missing)} questions missing, e.g. {missing[:5]}")
    if problems:
        sys.exit(f"ERROR: few-shot manifest {path} does not match this run:\n  - " + "\n  - ".join(problems)
                 + "\nDelete it to rebuild, or pass the right --fewshot/--fewshot-seed.")


def load_or_build_manifest(benchmark_path, questions: list[dict], k: int, seed: int,
                           path=None, ntok=None) -> tuple[dict, Path]:
    """Load the manifest for (benchmark, k, seed), building and saving it if absent.

    `questions` must be the FULL benchmark (exemplars are drawn from all of it),
    not a -n subset.
    """
    sha = benchmark_sha256(benchmark_path)
    path = Path(path) if path else manifest_path(benchmark_path, k, seed, sha)
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        validate_manifest(manifest, questions, sha, k, seed, path)
        return manifest, path
    manifest = build_manifest(questions, k, seed, ntok or load_reference_tokenizer())
    manifest["benchmark"] = Path(benchmark_path).name
    manifest["benchmark_version"] = fg._benchmark_version(benchmark_path)
    manifest["benchmark_sha256"] = sha
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    print(f"Built few-shot manifest: {path}")
    return manifest, path


# ---------------------------------------------------------------------------
# Prompt style
# ---------------------------------------------------------------------------

PROMPT_STYLES = ("chat", "completion")


def resolve_prompt_style(requested: str | None, backend: str, talkie_style: str | None = None) -> str:
    """Map (--prompt-style, backend) to a concrete renderer.

    Returns one of: 'api_chat', 'talkie_it', 'hf_chat', 'completion'.
    backend is 'openai' | 'openrouter' | 'talkie' | 'hf'.
    """
    if backend in ("openai", "openrouter"):
        if requested in (None, "chat"):
            return "api_chat"
        raise ValueError(f"--prompt-style {requested} is not supported for the {backend} backend (chat only).")
    if backend == "talkie":
        if talkie_style == "it":
            if requested in (None, "chat"):
                return "talkie_it"
            return "completion"
        if requested == "chat":
            raise ValueError("Talkie base has no chat template; use --prompt-style completion (the default).")
        return "completion"
    if requested is None:
        raise ValueError("Few-shot with a HuggingFace model needs an explicit --prompt-style "
                         "(chat for instruction-tuned models, completion for base models).")
    return "hf_chat" if requested == "chat" else "completion"


# ---------------------------------------------------------------------------
# Previews
# ---------------------------------------------------------------------------

def _fence(s: str) -> str:
    return "```text\n" + s + "\n```"


def preview_markdown(target: dict, manifest: dict, by_q: dict, ntok=None) -> str:
    prompt, entry = render_from_manifest(target, manifest, by_q)
    ex = [by_q[n] for n in entry["exemplars"]]
    sys0, user0, mt0, _ = fg.build_prompts(target)
    count = (lambda s: f"{ntok(s)} reference tokens. ") if ntok else (lambda s: "")
    L = [
        f"# Q{target['question_number']} — {target['reasoning_type']} ({target.get('frame_type', '')})",
        "",
        f"Pool `{entry['pool']}`; {entry['n_eligible']} eligible; k = {entry['k']} "
        f"(requested {manifest['k_requested']}); projected {entry['projected_tokens']}/{manifest['ceiling']}; "
        f"fallback {entry['fallback']}. Answer cap (max_new_tokens) {prompt.max_tokens}, same as zero-shot.",
        "",
        "| | type | source | author |", "|---|---|---|---|",
        *[f"| exemplar Q{e['question_number']} | {e['reasoning_type']} | `{e['source_htid']}` | {e.get('source_author', '')} |" for e in ex],
        f"| **target Q{target['question_number']}** | {target['reasoning_type']} | `{target['source_htid']}` | {target.get('source_author', '')} |",
        "", f"Ground truth (not shown to model): {target['answer_strings'][0]!r}", "",
        "## 1. Zero-shot, as the pipeline sends it today", "",
        "**system**", "", _fence(sys0), "", "**user**", "", _fence(user0), "",
        "## 2. Few-shot, chat (OpenAI / OpenRouter / HF-instruct)", "",
    ]
    for m in prompt.chat_messages():
        L += [f"**{m['role']}**", "", _fence(m["content"]), ""]
    L += ["## 3. Few-shot, Talkie-IT literal string", "", count(prompt.talkie_it_text()), "",
          _fence(prompt.talkie_it_text()), "",
          "## 4. Few-shot, completion (Talkie-base, HF base models)", "",
          count(prompt.completion_text) + "Stop strings: " + ", ".join(f"`{s!r}`" for s in BASE_STOPS) + ".", "",
          _fence(prompt.completion_text), ""]
    return "\n".join(L)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _load(path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "preview"):
        p = sub.add_parser(name)
        p.add_argument("benchmark")
        p.add_argument("--k", type=int, default=3)
        p.add_argument("--seed", type=int, default=0)
        p.add_argument("--manifest", default=None, help="Explicit manifest path (default: fewshot_manifests/...).")
        if name == "preview":
            p.add_argument("--qnum", type=int, nargs="+", required=True)
            p.add_argument("--out", default=None, help="Write Q###_type.md files here instead of printing.")
    args = ap.parse_args(argv)

    questions = _load(args.benchmark)
    manifest, path = load_or_build_manifest(args.benchmark, questions, args.k, args.seed, args.manifest)
    print(summarize(manifest))
    print(f"manifest: {path}")
    if args.cmd == "preview":
        by_q = {q["question_number"]: q for q in questions}
        try:
            ntok = load_reference_tokenizer()
        except RuntimeError:
            ntok = None
        for qn in args.qnum:
            md = preview_markdown(by_q[qn], manifest, by_q, ntok)
            if args.out:
                out = Path(args.out)
                out.mkdir(parents=True, exist_ok=True)
                (out / f"Q{qn:03d}_{by_q[qn]['reasoning_type']}.md").write_text(md, encoding="utf-8")
            else:
                print(md)


if __name__ == "__main__":
    main()
