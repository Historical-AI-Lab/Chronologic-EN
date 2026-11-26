# Few-shot prompting for free generation — design plan

Status: **implemented** in `../fewshot.py`, `free_generation.py` and `run_pipeline.py`.
Decisions taken after this draft: k is fixed at 3; world_qa draws are stratified (one
knowledge, one inference and one abstention exemplar, with the abstention exemplar
always an "insufficient information" refusal); LENGTH misalignment is accepted.
`examples/` is regenerated with `python fewshot.py preview`.

## 1. Where the change goes

Few-shot only affects **stage 8 (`free_generation.py`)**. Stages 9–12 judge the answer
against ground truth and never see the prompt. So:

- **New module `fewshot.py`**: exemplar eligibility, manifest builder, and the three
  renderers (chat, Talkie-IT, base). The prototype here becomes that module.
- **`free_generation.py`** gets `--fewshot-manifest PATH` and `--prompt-style {chat,completion}`.
  With no manifest, `build_prompts()` and every existing code path stay byte-identical
  (add a regression test for this).
- **`run_pipeline.py`** gets `--fewshot K` and `--fewshot-seed S`. It builds the manifest
  if it's missing (cheap, deterministic), passes it to stage 8, and **derives a distinct
  candidate label** (e.g. `talkie-1930-13b-base+fs3s0`), so few-shot answers never resume
  into, or overwrite, a zero-shot file. The ledger then separates the runs automatically.
  Also add a guard like `check_candidate_effort_matches_free_gen`: refuse to resume a
  free_gen file whose stored few-shot config differs from the one requested.

That means altering the existing scripts, not adding sibling scripts. The change is small
and off by default, and siblings would duplicate the backend plumbing (OpenAI,
OpenRouter, HF, Talkie).

## 2. Exemplar selection

**A frozen manifest, shared by every model.** It's built once per (benchmark, k, seed) and
maps each question number to its exemplars, its k after fallback, and its projected token
count. Every model reads the same manifest, so model comparisons aren't confounded by
which exemplars each model happened to draw. Each question uses its own RNG,
`Random(f"{seed}:{qnum}")`, so a question's exemplars don't change with file order or
with `-n` subsetting. The manifest records the benchmark's SHA-256, and stage 8 refuses
a mismatch.

**Eligible exemplars** for target *t*:

1. Same **pool** as *t*, where the pool is the reasoning_type, **except that knowledge,
   inference and abstention share one pool** (see §3).
2. Different source text, after normalizing IDs (`hvd.hn1eg5` = `hn1eg5` = `HN1EG5`).
   Five books carry two ID spellings in 1.0. None currently co-occur within a pool, but
   normalizing is cheap insurance.
3. Different `source_author`, when known. Seven authors span several htids within one
   reasoning type.
4. Not a near-duplicate prompt (Jaccard ≥ 0.6 on the first 20 words of `main_question`).
   **This matters:** six constrained_generation prompts recur almost verbatim across
   *different* sources (e.g. Q550/Q580, "current state of scientific opinion about the
   theories of Darwin"; Q446/449/569, "the fate of the soul after death"). Excluding only
   by source would hand the model a worked answer to its own question.

Your same-source rule is well founded: the only ground truths shared between questions
(five pairs of cloze items) are all within one source.

**Exemplar answer** = `answer_strings[0]`, verbatim. For the 86 questions with two
ground truths, always index 0.

**Order**: as sampled (random), target last.

Pool sizes after exclusions are comfortable everywhere: abstention, the smallest type,
draws from the ~230-question world-QA pool. No question has fewer than k eligible
exemplars in either the sample or the full file.

## 3. The abstention trap (the main design change from the brief)

57 of 62 abstention ground truths are the literal string `insufficient information`. A
pool restricted to abstention would show the model three refusals in a row before an
abstention question. That leaks the answer, and also the *task type*, which zero-shot
deliberately hides: knowledge, inference and abstention all use SYSTEM_PROMPT_A and a
world_context frame, so the model has to decide for itself whether to abstain.
Within-type pools would also bias the other direction, since knowledge and inference
questions would never see an abstention.

Pooling the three types keeps the decision honest. About 26% of exemplars will be
refusals, matching the base rate within the group, and the refusal rate is the same
whether the target is answerable or not. `examples/Q605_abstention.md` shows a draw
where an abstention target gets no refusal exemplars at all, which is the intended
behaviour.

## 4. Token budget: the 2048 ceiling barely binds

Computed with **Talkie's own BPE vocab as the reference tokenizer for every model**,
using the full rendered few-shot prompt (header, LENGTH lines, delimiters) plus a
projected answer window of `max(64, 1.5 × zero-shot max_tokens)` and a 64-token margin:

| | result on full 1.0 (866 q) |
|---|---|
| 3-shot fallbacks, seed 0 | **0** |
| max projected tokens | 1,832 / 2,048 |
| worst case (3 *largest* eligible exemplars, any question) | still fits |
| 4-shot fallbacks | 0 |
| 5-shot | ~7 questions fall back to 4 |

Typical exemplar sizes (median / max tokens): constrained_generation 135 / 409;
character_modeling 257 / 420; topic_sentence 250 / 490; knowledge 70 / 233.
Constrained-generation answers are long-ish, but the questions are short, so it isn't the
binding type. The cloze and topic-sentence passages are.

So the fallback stays in (it's a few lines, and it protects future benchmark versions and
larger k), but at k = 3 it won't fire. **Fallback rule:** drop the *last-sampled*
exemplar, not the longest, so the survivors aren't biased toward short exemplars on long
questions. Log `k`, `dropped`, and `fallback` per question in the manifest and in each
answer record, and print a fallback count at the end of the run.

Since there's headroom, **you could afford k = 4** for everything with no fallbacks. I'd
still start at 3 and treat k as an axis if the first result is interesting.

## 5. Base vs instruction-tuned formats

Yes, they should differ. Prompt style must be declared, not guessed from the model name:
`--prompt-style chat|completion`. Talkie reads `talkie_style.txt`/`MODELS[...].style`
automatically.

**Chat** (OpenAI, OpenRouter, Talkie-IT, HF-instruct): system message, then
(user, assistant) × k, then the target user turn. Exemplar answers go in real assistant
turns, the native few-shot format for chat models. Talkie-IT is rendered with its actual
`<|system|>`/`<|user|>`/`<|assistant|>` tokens (its CLI supports a system role).

**Completion** (Talkie-base, HF base models): one continuous document. A header holding
the same instruction text, then exemplar blocks separated by `* * *`, then the target
block ending `ANSWER:`. Notes:
- `* * *` never occurs in any question, frame, or answer. It's also the period section
  break Talkie will have seen in books. Blank lines can't serve as the delimiter: 434
  questions contain `\n\n`.
- Stop sequences: `\n* * *`, `\nCONTEXT:`, `<|endoftext|>`, plus post-hoc truncation at
  the same strings (`_generate_hf` has no stop-string support today).
- **No trailing space after `ANSWER:`.** Today's prompt ends `"ANSWER: "`. With this BPE,
  the space normally attaches to the *next* word, so a dangling space forces an unusual
  token boundary. That may contribute to zero-shot Talkie-base's degenerate
  `1. … 2. … 3. …` outputs (see `free_gen_talkie-1930-13b-base__0.7.json`).

This is the strongest reason to expect an effect: base models get almost nothing from an
instruction alone.

## 6. Prompt-design choices to decide

1. **Length guidance per item vs in the system prompt.** Today the system prompt carries
   the target's length_spec. With exemplars of different lengths that becomes
   contradictory, so the draft moves it to a `LENGTH:` line in every block (exemplars
   included) and reduces the system clause to "answer at the length given with each
   question." Wrinkle: LENGTH is computed from *all* answer options, not the ground
   truth, so an exemplar's answer sometimes misfits its own LENGTH line (Q495 in
   `Q765_constrained_generation.md`: "three to five sentences, 10–50 words" over a
   two-sentence, 25-word answer). I'd keep the same function for consistency with the
   target, but it's a judgment call.
2. **The "examples are from other books" sentence.** Exemplars come from other periods,
   so a model might imitate *their* period voice. The draft says so explicitly: "follow
   their form, but answer the final question from its own context." Worth keeping, but
   it's one more change versus zero-shot.
3. **Talkie-IT system turn.** Zero-shot currently puts the instructions inside the
   `<|user|>` turn. The draft uses `<|system|>`. The alternative is to keep everything in
   the first user turn.
4. **HF-instruct models.** Today they get **no chat template**, just a raw
   `system\nuser` string. For few-shot chat style, `apply_chat_template` is the honest
   choice, but it's another departure from the zero-shot baseline.
5. **Which frame is shown.** Exemplars use `metadata_frame`. The target uses
   `candidate_metadata_frame` when present, matching current behaviour.

## 7. Controls: separate "few-shot" from "new format"

Choices 1–4 all change the prompt *besides* adding exemplars. To attribute any gain to
the exemplars themselves, **run k = 0 in the new format** (the same renderer with an
empty exemplar list) alongside k = 3, at least for Talkie-base and one cheap chat model.
Then zero-shot-old → k0-new → k3-new decomposes the effect. The manifest with
`--fewshot 0` gives this for free.

**Exemplar-sampling variance.** Few-shot results are known to swing with which exemplars
are drawn. Run seeds 0 and 1 on one cheap model to size that variance before reading
differences between models.

## 8. Output and logging

Each answer record gains
`"fewshot": {"k", "k_requested", "exemplars", "dropped", "fallback", "projected_tokens",
"seed", "prompt_style", "manifest_sha256"}`, and the top level gains the same config. The
end-of-run summary prints the k distribution and the fallback count. The manifest is
written next to the free_gen output, named `fewshot_manifest__{bver}__k{K}_s{S}.json`.

## 9. Implementation steps

1. Promote the prototype to `modelasjudge/fewshot.py`. Tests: eligibility rules, per-q
   determinism, fallback, abstention pooling, byte-identical zero-shot path.
2. Wire `--fewshot-manifest` / `--prompt-style` into `free_generation.py`'s three
   generate functions. OpenAI Responses takes a message list as `input`; OpenRouter
   takes messages; HF/Talkie takes the rendered string plus stop strings.
3. Add stop-string truncation for the completion style.
4. `run_pipeline.py`: `--fewshot`, `--fewshot-seed`, derived label, manifest build, and
   resume guard. Check `--dry-run` output.
5. Pilot: Talkie-base and one API model at k ∈ {0, 3}, `-n 40`, to eyeball outputs before
   paying for judging.
