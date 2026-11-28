#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=gpuA100x4
#SBATCH --account=bdfx-delta-gpu
#SBATCH --time=06:00:00
#SBATCH --job-name=qwen7b-fs3
#SBATCH --error=qwen7b-fs3-%j.err
#SBATCH --output=qwen7b-fs3-%j.out
#SBATCH --gpus-per-node=1
#SBATCH --gpu-bind=closest
#SBATCH --mem=64g
#SBATCH --constraint="scratch"

# 3-shot free generation (stage 8 only) for Qwen2.5-7B-Instruct.
# Submit from modelasjudge/:   sbatch qwen7b_fewshot_A100.slurm
# Smoke test first (resumable): NQ=5 sbatch qwen7b_fewshot_A100.slurm
# Model from a local directory instead of the HF cache:
#   MODEL=/projects/bdfx/models/Qwen2.5-7B-Instruct sbatch qwen7b_fewshot_A100.slurm
#
# Label qwen25-7b-local-fs3s0 matches the published zero-shot label
# (qwen25-7b-local) plus the suffix run_pipeline.py derives from --fewshot 3,
# so stage 8 skips locally once the output is copied back. Instruct model, so
# the few-shot examples go in as chat turns through Qwen's chat template.
# Copy generated_answers/free_gen_qwen25-7b-local-fs3s0__1.0.json back and run
# stages 9-12 locally.

echo "Job starting on $(hostname)"
date

module reset
module load cudatoolkit/26.5_13.2
module list

source "$SLURM_SUBMIT_DIR/../../chronologic/evalcode/talkie-eval-env/bin/activate"

export HF_HOME=/work/nvme/bdfx/.cache/huggingface
export HF_HUB_OFFLINE=1

cd "$SLURM_SUBMIT_DIR"

MODEL=${MODEL:-Qwen/Qwen2.5-7B-Instruct}
BENCH=../booksample/chronologic_en_1.0.jsonl
MANIFEST=fewshot_manifests/fewshot_manifest__1.0__5c0547e5__k3_s0.json
[ -f "$BENCH" ] || { echo "ERROR: $BENCH missing (gated; copy it from the HF dataset)"; exit 1; }
[ -f "$MANIFEST" ] || { echo "ERROR: $MANIFEST missing (git pull?)"; exit 1; }

# Fail in seconds, not after queueing, if transformers or the weights are missing.
# HF_HUB_OFFLINE=1 means nothing is downloaded; a cache miss errors here.
python -c "
from transformers import AutoConfig
AutoConfig.from_pretrained('$MODEL')
print('model found: $MODEL')
" || { echo "ERROR: transformers missing from the env, or $MODEL not in $HF_HOME (set MODEL=/path/to/weights)"; exit 1; }

python -u free_generation.py \
    "$MODEL" \
    "$BENCH" \
    --candidate-label qwen25-7b-local-fs3s0 \
    --reasoning-effort none \
    --device cuda \
    --fewshot 3 --fewshot-seed 0 \
    --fewshot-manifest "$MANIFEST" \
    --prompt-style chat \
    ${NQ:+-n $NQ}

echo "Job completed"
date
