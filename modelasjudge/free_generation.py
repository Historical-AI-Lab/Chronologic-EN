"""
Free-generation evaluation of benchmark questions.

Poses questions to language models and collects open-ended text answers, rather
than scoring fixed answer options as benchmark_evaluation.py does. The answers
are written to a JSON file for evaluation by a separate scoring script.

Supported backends:
  HuggingFace transformers (local models, Apple Silicon / CUDA / CPU)
  OpenAI Responses API (GPT-4.1, GPT-5, fine-tuned variants)

Usage:
  # Print formatted prompts before running (recommended first step):
  python benchmark_free_generation.py path.jsonl --show-prompts

  # Print length-spec samples:
  python benchmark_free_generation.py path.jsonl --inspect

  # Run on OpenAI model:
  python benchmark_free_generation.py gpt-4.1-2025-04-14 path.jsonl

  # Run on local HF model (5 questions for testing):
  python benchmark_free_generation.py Qwen/Qwen2.5-7B-Instruct path.jsonl -n 5

Requires (HF path):     pip install torch transformers
Requires (OpenAI path): pip install openai  +  evalcode/credentials.txt
"""

import json
import math
import random
import re
import datetime
import statistics
from pathlib import Path
import sys
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Imports from benchmark_evaluation (shared infrastructure)
# ---------------------------------------------------------------------------

sys.path.append(str(Path(__file__).resolve().parent.parent / "evalcode"))


from benchmark_evaluation import (
    load_model,
    is_openai_model,
    load_openai_credentials,
    _call_responses_with_retry,
    _generate_hf,
)

# ---------------------------------------------------------------------------
# OpenRouter support
# ---------------------------------------------------------------------------

from openrouter_client import (
    is_openrouter_model,
    make_openrouter_client,
    call_openrouter_chat,
    always_reasons,
)
from naming import benchmark_version as _benchmark_version, candidate_tag as _candidate_tag
from naming import (
    FrameConditionError,
    condition_label as _condition_label,
    frame_condition_of_records as _frame_condition_of_records,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_A = (
    "You will be asked to answer a question in a way that fits the beliefs and "
    "expository style of a specific historical context. If the context described "
    "would not contain enough information to answer the question, respond simply "
    "'insufficient information.' Otherwise, answer in {length_spec}."
)

SYSTEM_PROMPT_B = (
    "Answer the question in a way that fits the beliefs and expository style of "
    "the historical context described. As a rough guideline, answer in {length_spec}."
)

_PROMPT_A_REASONING_TYPES = {"knowledge", "abstention", "inference"}


def _select_system_prompt(reasoning_type, answer_strings):
    if reasoning_type in _PROMPT_A_REASONING_TYPES:
        return SYSTEM_PROMPT_A
    for a in answer_strings:
        if isinstance(a, str):
            low = a.lower()
            if "insufficient information" in low or "i don't know" in low:
                return SYSTEM_PROMPT_A
    return SYSTEM_PROMPT_B


# ---------------------------------------------------------------------------
# Length-spec helpers
# ---------------------------------------------------------------------------

def extract_features(cleaned_answers):
    """Compute length and form features from a list of cleaned answer strings.

    Args:
        cleaned_answers: list of stripped answer strings.

    Returns:
        SimpleNamespace with fields:
            word_counts         — list[int], words per answer
            sentence_counts     — list[int], sentences per answer
            median_word_count   — float
            median_sentence_count — float
            proportion_sentence_like — float, fraction that look like sentences
            newline_count       — int, total newlines across all answers
    """
    word_counts = []
    sentence_counts = []
    sentence_like_count = 0
    total_newlines = 0

    for ans in cleaned_answers:
        words = ans.split()
        word_counts.append(len(words))

        # Split on sentence-ending punctuation
        parts = [p.strip() for p in re.split(r'[.!?]+', ans) if p.strip()]
        sentence_counts.append(max(1, len(parts)))

        # "Sentence-like": ends with terminal punctuation or has >= 8 words
        if re.search(r'[.!?]\s*$', ans) or len(words) >= 8:
            sentence_like_count += 1

        total_newlines += ans.count('\n')

    n = len(cleaned_answers)
    median_wc = statistics.median(word_counts) if word_counts else 0
    median_sc = statistics.median(sentence_counts) if sentence_counts else 1
    prop_sentence = sentence_like_count / n if n > 0 else 0.0

    return SimpleNamespace(
        word_counts=word_counts,
        sentence_counts=sentence_counts,
        median_word_count=median_wc,
        median_sentence_count=median_sc,
        proportion_sentence_like=prop_sentence,
        newline_count=total_newlines,
    )


def clamp_and_round(value, form, direction='nearest'):
    """Round value to a natural step size and clamp to a form minimum.

    Args:
        value:     raw numeric value (may be fractional).
        form:      one of 'verse', 'short_phrase', 'single_sentence',
                   'multi_sentence', 'phrase_or_sentence'.
        direction: 'floor' rounds down (for lower bounds),
                   'ceil'  rounds up   (for upper bounds),
                   'nearest' rounds to closest step (default).

    Returns:
        int: rounded, clamped value >= the form's minimum.
    """
    config = {
        'verse':              (1,  1),
        'short_phrase':       (1,  1),
        'single_sentence':    (10, 10),
        'multi_sentence':     (10, 10),
        'phrase_or_sentence': (3,  5),
    }
    minimum, step = config.get(form, (3, 5))
    if step <= 1:
        return int(max(minimum, round(value)))
    if direction == 'floor':
        return int(max(minimum, math.floor(value / step) * step))
    if direction == 'ceil':
        return int(max(minimum, math.ceil(value / step) * step))
    return int(max(minimum, round(value / step) * step))


def verbal_sentence_range(median_sent_count):
    """Convert a median sentence count to a verbal description.

    Args:
        median_sent_count: float.

    Returns:
        str: e.g. "one to two sentences".
    """
    if median_sent_count <= 1.5:
        return "one to two sentences"
    elif median_sent_count <= 2.5:
        return "two to three sentences"
    elif median_sent_count <= 4.0:
        return "three to five sentences"
    else:
        return "a short paragraph"


def make_length_spec(answer_strings, question_category):
    """Derive a verbal length guideline and max-token ceiling from sample answers.

    Does not pass the answer options to the model; they only guide the length hint.

    Args:
        answer_strings:    list of candidate answer strings (index 0 = ground truth).
        question_category: question category string (e.g. 'poetry', 'cloze_causal').

    Returns:
        tuple: (upper, length_spec_string)
            upper             — int; caller should set max_new_tokens = upper * 2
            length_spec_string — str; inserted into SYSTEM_PROMPT
    """
    if not answer_strings:
        return 50, "about 20\u201350 words"

    cleaned = [s.strip() for s in answer_strings if s.strip()]
    if not cleaned:
        return 50, "about 20\u201350 words"

    features = extract_features(cleaned)

    # --- Form detection ---
    if features.newline_count > 0 and 'poet' in (question_category or '').lower():
        form = 'verse'
    elif (features.median_word_count <= 6
          and features.proportion_sentence_like < 0.5):
        form = 'short_phrase'
    elif features.proportion_sentence_like >= 0.6:
        if features.median_sentence_count <= 1.5:
            form = 'single_sentence'
        else:
            form = 'multi_sentence'
    else:
        form = 'phrase_or_sentence'

    # --- Length summary ---
    counts = sorted(features.word_counts)
    if len(counts) >= 2:
        q1 = statistics.median(counts[:len(counts)//2])
        q3 = statistics.median(counts[(len(counts)+1)//2:])
    else:
        q1 = q3 = counts[0] if counts else 20

    lower = clamp_and_round(q1, form, direction='floor')
    upper = clamp_and_round(q3, form, direction='ceil')

    # If actual data starts below a lower bound of 10, pull the lower bound down
    # to reflect where the answers actually begin: clamp to 5 if min >= 5,
    # otherwise use the actual minimum directly.
    actual_min = counts[0]
    if lower == 10 and actual_min < 10:
        lower = 5 if actual_min >= 5 else actual_min

    # Ensure lower < upper
    if lower >= upper:
        lower = max(1, upper - (10 if upper >= 20 else 5 if upper >= 5 else 1))

    # --- Sentence vs phrase labeling ---
    # If no sample answer starts with a capital letter, call it a "phrase".
    none_capitalized = not any(s[0].isupper() for s in cleaned if s)
    unit = 'phrase' if none_capitalized else 'sentence'

    # --- Verbalization ---
    if form == 'verse':
        return 75, "lines of verse, as specified in the question"

    if form == 'short_phrase':
        if upper <= 3:
            return upper, "a few words"
        else:
            return upper, f"a short phrase of about {lower}\u2013{upper} words"

    if form == 'single_sentence':
        return upper, f"one {unit} of about {lower}\u2013{upper} words"

    if form == 'multi_sentence':
        sent_range = verbal_sentence_range(features.median_sentence_count)
        if unit == 'phrase':
            sent_range = sent_range.replace('sentences', 'phrases').replace('sentence', 'phrase')
        return upper, f"{sent_range}, about {lower}\u2013{upper} words total"

    # phrase_or_sentence fallback
    return upper, f"about {lower}\u2013{upper} words"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompts(question):
    """Build system and user prompts for a free-generation question.

    Args:
        question: dict with keys 'metadata_frame', 'main_question',
                  'answer_strings', 'question_category'.

    Returns:
        tuple: (system_str, user_str, max_tokens)
            system_str — system prompt with length_spec filled in
            user_str   — CONTEXT / QUESTION / ANSWER: block
            max_tokens — int; hard ceiling = upper * 2
    """
    upper, length_spec = make_length_spec(
        question.get('answer_strings', []),
        question.get('question_category', ''),
    )
    template = _select_system_prompt(
        question.get('reasoning_type', ''),
        question.get('answer_strings', []),
    )
    system_str = template.format(length_spec=length_spec)
    user_str = (
        "CONTEXT: " + (question.get('candidate_metadata_frame') or question.get('metadata_frame', ''))
        + "\nQUESTION: " + question.get('main_question', '')
        + "\nANSWER: "
    )
    return system_str, user_str, max(16, upper * 2), length_spec


# ---------------------------------------------------------------------------
# Generation functions
# ---------------------------------------------------------------------------

def generate_answer_openai(question, model_id, client, reasoning_effort="none"):
    """Generate a free-text answer via the OpenAI Responses API.

    Args:
        question:         benchmark question dict.
        model_id:         OpenAI model identifier string.
        client:           openai.OpenAI instance.
        reasoning_effort: one of "none", "minimal", "low", "medium", "high".

    Returns:
        tuple: (answer_str, length_spec_str)
    """
    system_str, user_str, max_tokens, length_spec = build_prompts(question)
    # For reasoning models, max_output_tokens covers thinking + answer combined.
    # Use 25000 whenever reasoning is active so thinking tokens don't crowd out
    # the answer; the length_spec in the system prompt still constrains length.
    effective_max_tokens = max_tokens if reasoning_effort == "none" else 25000
    response = _call_responses_with_retry(
        client, model_id, user_str, system_str,
        max_output_tokens=effective_max_tokens,
        reasoning_effort=reasoning_effort,
        text_format=None,
    )
    return (response.output_text or "").strip(), length_spec


def generate_answer_hf(question, model, tokenizer):
    """Generate a free-text answer using a HuggingFace causal LM.

    Prepends the system prompt to the user prompt since HF causal LMs have no
    separate system prompt channel.

    Args:
        question:  benchmark question dict.
        model:     loaded HF AutoModelForCausalLM in eval mode.
        tokenizer: matching AutoTokenizer.

    Returns:
        tuple: (answer_str, length_spec_str)
    """
    system_str, user_str, max_tokens, length_spec = build_prompts(question)
    full_prompt = system_str + "\n" + user_str
    answer = _generate_hf(full_prompt, model, tokenizer, max_new_tokens=max_tokens)
    return answer.strip(), length_spec


def generate_answer_openrouter(question, model_id, client, reasoning_effort="none"):
    """Generate a free-text answer via the OpenRouter API.

    Args:
        question:         benchmark question dict.
        model_id:         OpenRouter model identifier string (e.g. ``qwen/qwen3-8b``).
        client:           openai.OpenAI instance pointed at OpenRouter base URL.
        reasoning_effort: one of "none", "minimal", "low", "medium", "high", "max".

    Returns:
        tuple: (answer_str, length_spec_str, downgraded_bool)
            downgraded_bool — True if the model hit the length cap while thinking
            and the call was silently retried with reasoning disabled.
    """
    system_str, user_str, max_tokens, length_spec = build_prompts(question)
    # Some OpenRouter models (e.g. deepseek-r1-distill) always emit visible
    # chain-of-thought regardless of the reasoning_effort flag; the answer-sized
    # cap from build_prompts is nowhere near enough budget for those.
    if always_reasons(model_id) or reasoning_effort == "max":
        max_tokens = max(max_tokens, 25000)
    answer, meta = call_openrouter_chat(
        client, model_id,
        user_content=user_str,
        system_content=system_str,
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        return_meta=True,
    )
    return answer.strip(), length_spec, meta["downgraded"]


# ---------------------------------------------------------------------------
# Few-shot generation (see fewshot.py). The zero-shot functions above are
# untouched; these take a pre-rendered fewshot.FewShotPrompt instead.
# ---------------------------------------------------------------------------

def generate_fewshot_openai(prompt, model_id, client, reasoning_effort="none"):
    """Responses API: exemplars go in `input` as prior user/assistant turns."""
    effective_max_tokens = prompt.max_tokens if reasoning_effort == "none" else 25000
    response = _call_responses_with_retry(
        client, model_id, prompt.turns, prompt.system,
        max_output_tokens=effective_max_tokens,
        reasoning_effort=reasoning_effort,
        text_format=None,
    )
    return (response.output_text or "").strip()


def generate_fewshot_openrouter(prompt, model_id, client, reasoning_effort="none"):
    max_tokens = prompt.max_tokens
    if always_reasons(model_id) or reasoning_effort == "max":
        max_tokens = max(max_tokens, 25000)
    answer, meta = call_openrouter_chat(
        client, model_id, user_content=None,
        messages=prompt.chat_messages(),
        max_tokens=max_tokens,
        reasoning_effort=reasoning_effort,
        return_meta=True,
    )
    return answer.strip(), meta["downgraded"]


def generate_fewshot_hf(prompt, style, model, tokenizer):
    """Local models (HF or Talkie), greedy, with the prompt rendered per style.

    Bypasses _generate_hf because that applies Talkie-IT's single-user-turn
    wrapper; here the full multi-turn string is built explicitly.
    """
    import torch
    from benchmark_evaluation import _input_device
    import fewshot

    if style == "hf_chat":
        input_ids = tokenizer.apply_chat_template(
            prompt.chat_messages(), add_generation_prompt=True, return_tensors="pt")
    else:
        text = prompt.talkie_it_text() if style == "talkie_it" else prompt.completion_text
        input_ids = tokenizer(text, return_tensors="pt").input_ids
    input_ids = input_ids.to(_input_device(model))
    with torch.no_grad():
        output_ids = model.generate(input_ids, max_new_tokens=prompt.max_tokens, do_sample=False)
    raw = tokenizer.decode(output_ids[0, input_ids.shape[1]:], skip_special_tokens=True)
    return fewshot.truncate_at_stops(raw).strip()


# ---------------------------------------------------------------------------
# Output normalization
# ---------------------------------------------------------------------------

def normalize_answer(answer, answer_strings):
    """Normalize a model reply to match the formatting conventions of sample answers.

    Currently: if none of the sample answers end with terminal punctuation,
    silently strips any trailing punctuation from the model's reply.
    Capitalization is left untouched (proper nouns may appear first).

    Args:
        answer:         the model's raw reply string.
        answer_strings: list of sample answer strings from the benchmark question.

    Returns:
        str: normalized answer.
    """
    cleaned = [s.strip() for s in answer_strings if s.strip()]
    if cleaned and not any(re.search(r'[.!?]\s*$', s) for s in cleaned):
        answer = re.sub(r'[.!?]+\s*$', '', answer).rstrip()
    return answer


# ---------------------------------------------------------------------------
# Inspection utilities
# ---------------------------------------------------------------------------

def inspect_length_specs(path_to_jsonl, n=20):
    """Print length-spec samples for human inspection.

    Args:
        path_to_jsonl: path to benchmark JSONL file.
        n:             number of questions to sample.
    """
    questions = _load_questions(path_to_jsonl)
    sample = random.sample(questions, min(n, len(questions)))

    print(f"\n{'='*70}")
    print(f"LENGTH SPEC INSPECTION  ({len(sample)} questions from {path_to_jsonl})")
    print('='*70)

    for i, q in enumerate(sample, 1):
        upper, spec = make_length_spec(
            q.get('answer_strings', []),
            q.get('question_category', ''),
        )
        print(f"\n--- Question {i} (category: {q.get('question_category', '?')}) ---")
        print("Answer strings:")
        for ans in q.get('answer_strings', []):
            print(f"  {ans!r}")
        print(f"→ length_spec: {spec!r}  (upper={upper}, max_tokens={upper*2})")

    print(f"\n{'='*70}\n")


def show_sample_prompts(path_to_jsonl, n=5):
    """Print full formatted prompts for human inspection before running.

    Shows exactly what the model will receive: the system prompt and the
    user-facing CONTEXT / QUESTION / ANSWER block.

    Args:
        path_to_jsonl: path to benchmark JSONL file.
        n:             number of questions to sample.
    """
    questions = _load_questions(path_to_jsonl)
    sample = random.sample(questions, min(n, len(questions)))

    print(f"\n{'='*70}")
    print(f"PROMPT PREVIEW  ({len(sample)} questions from {path_to_jsonl})")
    print('='*70)

    for i, q in enumerate(sample, 1):
        system_str, user_str, max_tokens, length_spec = build_prompts(q)
        print(f"\n{'─'*70}")
        print(f"Question {i}  |  category: {q.get('question_category', '?')}  |  max_tokens: {max_tokens}")
        print(f"{'─'*70}")
        print("[SYSTEM PROMPT]")
        print(system_str)
        print()
        print("[USER PROMPT]")
        print(user_str)
        print()
        print(f"[GROUND TRUTH]  {q.get('answer_strings', ['?'])[0]!r}")

    print(f"\n{'='*70}\n")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_questions(path_to_jsonl):
    """Load all questions from a JSONL file.

    Args:
        path_to_jsonl: str or Path.

    Returns:
        list of question dicts.
    """
    questions = []
    with open(path_to_jsonl, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def _sanitize_model_id(model_id):
    """Convert a model ID to a filesystem-safe string."""
    return re.sub(r'[^a-zA-Z0-9_\-.]', '_', model_id)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

_GENERATED_DIR = Path(__file__).parent / "generated_answers"


def resolve_frame_condition(all_questions, candidate_label, *, output_path=None, fewshot_k=None):
    """Return (condition, label) for a benchmark that may carry candidate frames.

    A benchmark variant whose records carry `candidate_metadata_frame` shows the
    candidate a different context than the judge grades against. Its answers
    must never land under the real run's label, so the label gets a
    '-{condition}' suffix here (added once). Raises SystemExit if the variant
    is unmarked, if an explicit --output path would bypass the suffix, or if
    few-shot is requested (exemplars would show variant frames over period
    answers, which is not the condition being tested).
    """
    try:
        condition = _frame_condition_of_records(all_questions)
    except FrameConditionError as exc:
        sys.exit(f"ERROR: {exc}")
    if condition is None:
        return None, candidate_label
    if fewshot_k is not None:
        sys.exit(f"ERROR: benchmark carries candidate_frame_condition={condition!r}; "
                 f"few-shot is not supported for candidate-frame variants.")
    label = _condition_label(candidate_label, condition)
    if output_path is not None and f"-{condition}" not in Path(output_path).name:
        sys.exit(f"ERROR: --output {output_path} lacks '-{condition}' in its filename, but the "
                 f"benchmark carries candidate_frame_condition={condition!r}. Omit --output "
                 f"(the auto-named file uses label {label!r}) or include the suffix.")
    return condition, label


def check_resume_condition(existing, condition, output_path):
    """Refuse to resume into a file generated under a different frame condition."""
    existing_cond = existing.get("candidate_frame_condition")
    if existing_cond != condition:
        sys.exit(
            f"ERROR: {output_path} was generated with candidate_frame_condition="
            f"{existing_cond!r}, but this benchmark has {condition!r}. Resuming would mix "
            f"answers written under different contexts in one file.")


def run_free_generation(
    model_id,
    path_to_jsonl,
    output_path=None,
    output_dir=None,
    credentials_path=None,
    openrouter_credentials_path=None,
    force_openrouter=False,
    reasoning_effort="none",
    quantize=None,
    lora_adapter=None,
    trust_remote_code=False,
    num_questions=None,
    device=None,
    device_map=None,
    candidate_label=None,
    fewshot_k=None,
    fewshot_seed=0,
    fewshot_manifest=None,
    prompt_style=None,
):
    """Generate free-text answers for benchmark questions and write a JSON report.

    Detects HuggingFace vs OpenAI vs OpenRouter backend from model_id.  Resumes
    automatically if the output file already exists (skips already-answered
    question_numbers).  Writes the output JSON after every answer so a crash
    loses at most one answer.

    Args:
        model_id:                    HF model path/ID, OpenAI model ID, or OpenRouter model ID.
        path_to_jsonl:               path to benchmark JSONL file.
        output_path:                 exact output JSON path; overrides output_dir if given.
        output_dir:                  directory for auto-named output; defaults to generated_answers/.
        credentials_path:            path to OpenAI credentials file; None = default.
        openrouter_credentials_path: path to OpenRouter credentials file; None = default.
        force_openrouter:            route through OpenRouter even if prefix not detected.
        reasoning_effort:            OpenAI Responses API reasoning effort.
        quantize:                    'int4' or 'int8' for HF torchao quantization; None = off.
        lora_adapter:                path to LoRA adapter; None = off.
        trust_remote_code:           passed to HF from_pretrained.
        num_questions:               cap on questions to process (for testing).
        device_map:                  passed to HF from_pretrained for multi-GPU sharding
                                     (e.g. 'auto'); overrides device when set.
        candidate_label:             Human-readable label for the candidate (used in filenames
                                     and downstream metadata).  Defaults to model_id.  Use this
                                     to distinguish fine-tuned variants from their base model
                                     (e.g. 'Qwen2.5-7B-Instruct-ft').
        fewshot_k:                   None = zero-shot (unchanged legacy prompts). An int k
                                     (0 included: the new-format control) turns on few-shot
                                     prompting with the shared exemplar manifest (fewshot.py).
        fewshot_seed:                seed selecting the manifest.
        fewshot_manifest:            explicit manifest path; default fewshot_manifests/...,
                                     built on first use.
        prompt_style:                'chat' or 'completion'; required for few-shot with plain
                                     HF models, inferred for API backends and Talkie.

    Returns:
        str: absolute path to the written JSON output file.
    """
    if candidate_label is None:
        candidate_label = model_id

    all_questions = _load_questions(path_to_jsonl)
    frame_condition, candidate_label = resolve_frame_condition(
        all_questions, candidate_label, output_path=output_path, fewshot_k=fewshot_k)
    questions = all_questions
    if num_questions is not None:
        questions = questions[:num_questions]

    fs_manifest = fs_manifest_path = None
    by_qnum = {q.get('question_number'): q for q in all_questions}
    if fewshot_k is not None:
        import fewshot
        # Exemplars come from the whole benchmark, never just the -n subset.
        fs_manifest, fs_manifest_path = fewshot.load_or_build_manifest(
            path_to_jsonl, all_questions, fewshot_k, fewshot_seed, fewshot_manifest)
        print(fewshot.summarize(fs_manifest))

    bver = _benchmark_version(path_to_jsonl)
    bpath = str(Path(path_to_jsonl).resolve())

    # Auto-name output file using stable {candidate}__{version} convention.
    if output_path is None:
        ctag = _candidate_tag(candidate_label)
        out_dir = Path(output_dir) if output_dir else _GENERATED_DIR
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / f"free_gen_{ctag}__{bver}.json"
    output_path = Path(output_path)

    # Determine backend
    use_openai = is_openai_model(model_id)
    use_openrouter = (not use_openai) and (force_openrouter or is_openrouter_model(model_id))

    # Few-shot config is fixed before any model loads, so a mismatch with an
    # existing output file fails at second 0.
    fs_config = None
    if fs_manifest is not None:
        import fewshot
        if use_openai or use_openrouter:
            backend, talkie_style = ("openai" if use_openai else "openrouter"), None
        else:
            from talkie_backend import is_talkie_model, _resolve_talkie_paths
            if is_talkie_model(model_id):
                backend, talkie_style = "talkie", _resolve_talkie_paths(model_id)[2]
            else:
                backend, talkie_style = "hf", None
        try:
            resolved_style = fewshot.resolve_prompt_style(prompt_style, backend, talkie_style)
        except ValueError as exc:
            sys.exit(f"ERROR: {exc}")
        fs_config = {
            "k": fewshot_k,
            "seed": fewshot_seed,
            "prompt_style": resolved_style,
            "manifest": Path(fs_manifest_path).name,
            "benchmark_sha256": fs_manifest["benchmark_sha256"],
            "rules_version": fs_manifest["rules_version"],
        }
        print(f"Few-shot: k={fewshot_k} seed={fewshot_seed} prompt_style={resolved_style}")

    # Load existing results for resume
    if output_path.exists():
        with open(output_path, encoding='utf-8') as fh:
            existing = json.load(fh)
        check_resume_condition(existing, frame_condition, output_path)
        existing_fs = existing.get('fewshot')
        if existing_fs != fs_config:
            sys.exit(
                f"ERROR: {output_path} was generated with fewshot={existing_fs!r}, but this run "
                f"requests fewshot={fs_config!r}. Resuming would mix prompt formats in one file. "
                f"Use a distinct --candidate-label (run_pipeline.py derives one automatically "
                f"from --fewshot), or move the old file aside."
            )
        already_answered = set(existing.get('answers', {}).keys())
        answers = existing.get('answers', {})
        print(f"Resuming: {len(already_answered)} questions already answered.")
    else:
        already_answered = set()
        answers = {}

    output_data = {
        "model": model_id,
        "candidate_label": candidate_label,
        "benchmark_version": bver,
        "benchmark_path": bpath,
        "lora_adapter": lora_adapter,
        "reasoning_effort": reasoning_effort,
        "answers": answers,
    }
    if fs_config is not None:
        output_data["fewshot"] = fs_config
    if frame_condition is not None:
        output_data["candidate_frame_condition"] = frame_condition

    if use_openai:
        org_id, api_key = load_openai_credentials(credentials_path)
        from openai import OpenAI
        client = OpenAI(organization=org_id, api_key=api_key)
        hf_model = hf_tokenizer = None
        print(f"Using OpenAI model: {model_id}")
    elif use_openrouter:
        client = make_openrouter_client(openrouter_credentials_path)
        hf_model = hf_tokenizer = None
        print(f"Using OpenRouter model: {model_id}")
    else:
        print(f"Loading model: {model_id}")
        hf_model, hf_tokenizer = load_model(
            model_id,
            device=device,
            device_map=device_map,
            trust_remote_code=trust_remote_code,
            quantize=quantize,
            lora_adapter=lora_adapter,
        )
        client = None

    n_overridden = sum(1 for q in questions if q.get('candidate_metadata_frame'))
    if n_overridden:
        print(f"\n*** {n_overridden}/{len(questions)} questions use candidate_metadata_frame "
              f"(condition {frame_condition!r}, label {candidate_label!r}) -- the candidate "
              f"is being shown a DIFFERENT context than the judge will grade against. ***\n")

    # Generate answers
    total = len(questions)
    for idx, q in enumerate(questions):
        qnum = str(q.get('question_number', idx))
        if qnum in already_answered:
            continue

        print(f"  [{idx + 1}/{total}] question_number={qnum}", end=' ', flush=True)

        fs_record = None
        if fs_config is not None:
            prompt, entry = fewshot.render_from_manifest(q, fs_manifest, by_qnum)
            length_spec = prompt.length_spec
            downgraded = False
            style = fs_config["prompt_style"]
            if use_openai:
                answer = generate_fewshot_openai(prompt, model_id, client, reasoning_effort)
            elif use_openrouter:
                answer, downgraded = generate_fewshot_openrouter(prompt, model_id, client, reasoning_effort)
            else:
                answer = generate_fewshot_hf(prompt, style, hf_model, hf_tokenizer)
            fs_record = {k: entry[k] for k in ("k", "exemplars", "exemplar_types", "dropped",
                                               "fallback", "short_pool", "projected_tokens")}
        elif use_openai:
            answer, length_spec = generate_answer_openai(
                q, model_id, client, reasoning_effort=reasoning_effort
            )
            downgraded = False
        elif use_openrouter:
            answer, length_spec, downgraded = generate_answer_openrouter(
                q, model_id, client, reasoning_effort=reasoning_effort
            )
        else:
            answer, length_spec = generate_answer_hf(q, hf_model, hf_tokenizer)
            downgraded = False

        answer = normalize_answer(answer, q.get('answer_strings', []))
        print(f"→ {answer[:60]!r}{'...' if len(answer) > 60 else ''}")

        gt_indices = [
            i for i, t in enumerate(q.get('answer_types', []))
            if t == 'ground_truth'
        ]
        ground_truths = [q['answer_strings'][i] for i in gt_indices] if gt_indices else [q.get('answer_strings', [''])[0]]
        answers[qnum] = {
            "metadata_frame": q.get('metadata_frame', ''),
            "candidate_metadata_frame_used": q.get('candidate_metadata_frame')
                                              or q.get('metadata_frame', ''),
            "main_question": q.get('main_question', ''),
            "ground_truths": ground_truths,
            "reasoning_type": q.get('reasoning_type', ''),
            "length_spec": length_spec,
            "answer": answer,
            "reasoning_downgraded": downgraded,
        }
        if fs_record is not None:
            answers[qnum]["fewshot"] = fs_record

        # Write after every answer (crash-safe)
        with open(output_path, 'w', encoding='utf-8') as fh:
            json.dump(output_data, fh, indent=2, ensure_ascii=False)

    n_downgraded = sum(1 for a in answers.values() if a.get('reasoning_downgraded'))
    if n_downgraded:
        print(
            f"\n{n_downgraded}/{len(answers)} answers had reasoning disabled after "
            f"hitting the length cap at reasoning_effort={reasoning_effort!r}."
        )
    if fs_config is not None:
        n_fb = sum(1 for a in answers.values() if a.get('fewshot', {}).get('fallback'))
        n_sp = sum(1 for a in answers.values() if a.get('fewshot', {}).get('short_pool'))
        print(f"\nFew-shot: {n_fb}/{len(answers)} answers fell back below k={fewshot_k} "
              f"(token ceiling); {n_sp} had too few eligible exemplars.")
    print(f"\nDone. Results written to: {output_path.resolve()}")
    return str(output_path.resolve())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Free-generation evaluation of benchmark questions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'model_id', nargs='?',
        help="HF model path/ID, OpenAI model ID, or OpenRouter model ID "
             "(e.g. qwen/qwen3-8b). Omit with --inspect/--show-prompts.",
    )
    parser.add_argument(
        'path_to_jsonl',
        help="Path to benchmark JSONL question file.",
    )
    parser.add_argument(
        '--inspect', action='store_true',
        help="Print length-spec samples for 20 random questions and exit.",
    )
    parser.add_argument(
        '--show-prompts', action='store_true',
        help="Print full formatted prompts for 5 random questions and exit.",
    )
    parser.add_argument(
        '--output', metavar='PATH',
        help="Override output JSON file path.",
    )
    parser.add_argument(
        '--output-dir', metavar='DIR',
        help="Directory for auto-named output (default: modelasjudge/generated_answers/).",
    )
    parser.add_argument(
        '--credentials', metavar='PATH',
        help="Path to OpenAI credentials file (default: evalcode/credentials.txt).",
    )
    parser.add_argument(
        '--openrouter', action='store_true',
        help="Force routing through OpenRouter even if model prefix is not detected.",
    )
    parser.add_argument(
        '--openrouter-credentials', metavar='PATH', dest='openrouter_credentials',
        help="Path to OpenRouter credentials file "
             "(default: bertclassify/OpenRouterCredentials.txt).",
    )
    parser.add_argument(
        '--reasoning-effort',
        choices=['none', 'minimal', 'low', 'medium', 'high', 'max'],
        default='none',
        help="OpenAI Responses API reasoning effort (default: none).",
    )
    parser.add_argument(
        '--quantize', choices=['int4', 'int8'],
        help="HF model quantization via torchao.",
    )
    parser.add_argument(
        '--lora-adapter', metavar='PATH',
        help="Path to LoRA adapter checkpoint (HF only).",
    )
    parser.add_argument(
        '--trust-remote-code', action='store_true',
        help="Pass trust_remote_code=True to HF from_pretrained.",
    )
    parser.add_argument(
        '-n', '--num-questions', type=int, metavar='N',
        help="Process only the first N questions (useful for testing).",
    )
    parser.add_argument(
        '--device', choices=['cpu', 'mps', 'cuda'],
        help="Device for local models (default: auto-detect cuda > mps > cpu).",
    )
    parser.add_argument(
        '--device-map', metavar='MAP', dest='device_map',
        help="HF device_map for multi-GPU sharding (e.g. 'auto').",
    )
    parser.add_argument(
        '--candidate-label', metavar='LABEL', dest='candidate_label', default=None,
        help="Human-readable label stored in the output JSON and used in filenames. "
             "Use to distinguish fine-tuned variants from their base model "
             "(e.g. 'Qwen2.5-7B-Instruct-ft'). Defaults to model_id.",
    )
    parser.add_argument(
        '--fewshot', type=int, metavar='K', default=None,
        help="Few-shot prompting with K worked examples per question (see fewshot.py). "
             "K=0 gives the new prompt format with no examples (control). Omit for the "
             "legacy zero-shot prompts.",
    )
    parser.add_argument(
        '--fewshot-seed', type=int, default=0, metavar='S',
        help="Seed selecting the exemplar manifest (default 0).",
    )
    parser.add_argument(
        '--fewshot-manifest', metavar='PATH', default=None,
        help="Explicit exemplar manifest (default: fewshot_manifests/, built on first use).",
    )
    parser.add_argument(
        '--prompt-style', choices=['chat', 'completion'], default=None,
        help="Few-shot prompt format. Inferred for API models (chat) and Talkie "
             "(chat for -it, completion for base); required for other HF models.",
    )

    args = parser.parse_args()

    if args.inspect:
        inspect_length_specs(args.path_to_jsonl)
        return

    if args.show_prompts:
        show_sample_prompts(args.path_to_jsonl)
        return

    if not args.model_id:
        parser.error("model_id is required unless --inspect or --show-prompts is set.")

    run_free_generation(
        model_id=args.model_id,
        path_to_jsonl=args.path_to_jsonl,
        output_path=args.output,
        output_dir=args.output_dir,
        credentials_path=args.credentials,
        openrouter_credentials_path=args.openrouter_credentials,
        force_openrouter=args.openrouter,
        reasoning_effort=args.reasoning_effort,
        quantize=args.quantize,
        lora_adapter=args.lora_adapter,
        trust_remote_code=args.trust_remote_code,
        num_questions=args.num_questions,
        device=args.device,
        device_map=args.device_map,
        candidate_label=args.candidate_label,
        fewshot_k=args.fewshot,
        fewshot_seed=args.fewshot_seed,
        fewshot_manifest=args.fewshot_manifest,
        prompt_style=args.prompt_style,
    )


if __name__ == '__main__':
    main()
