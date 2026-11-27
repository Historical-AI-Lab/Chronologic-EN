#!/bin/bash
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=gpuA100x4
#SBATCH --account=bdfx-delta-gpu
#SBATCH --time=12:00:00
#SBATCH --job-name=talkie-it-fs3
#SBATCH --error=talkie-it-fs3-%j.err
#SBATCH --output=talkie-it-fs3-%j.out
#SBATCH --gpus-per-node=1
#SBATCH --gpu-bind=closest
#SBATCH --mem=128g
#SBATCH --constraint="scratch"

# 3-shot free generation (stage 8 only) for talkie-1930-13b-it.
# Submit from modelasjudge/:   sbatch talkie_it_fewshot_A100.slurm
# Smoke test first (resumable): NQ=5 sbatch talkie_it_fewshot_A100.slurm
#
# Uses the frozen manifest in fewshot_manifests/, so every model sees the same
# exemplars. The label must stay MODEL-fs3s0: that is what run_pipeline.py
# derives from --fewshot 3, so its stage 8 finds this file and skips.
# Copy generated_answers/free_gen_talkie-1930-13b-it-fs3s0__1.0.json back
# and run stages 9-12 locally.

echo "Job starting on $(hostname)"
date

module reset
module load cudatoolkit/26.5_13.2
module list

source "$SLURM_SUBMIT_DIR/../../chronologic/evalcode/talkie-eval-env/bin/activate"

export HF_HOME=/work/nvme/bdfx/.cache/huggingface
export HF_HUB_OFFLINE=1

cd "$SLURM_SUBMIT_DIR"

BENCH=../booksample/chronologic_en_1.0.jsonl
MANIFEST=fewshot_manifests/fewshot_manifest__1.0__5c0547e5__k3_s0.json
[ -f "$BENCH" ] || { echo "ERROR: $BENCH missing (gated; copy it from the HF dataset)"; exit 1; }
[ -f "$MANIFEST" ] || { echo "ERROR: $MANIFEST missing (git pull?)"; exit 1; }

python -u free_generation.py \
    talkie-1930-13b-it \
    "$BENCH" \
    --candidate-label talkie-1930-13b-it-fs3s0 \
    --reasoning-effort none \
    --fewshot 3 --fewshot-seed 0 \
    --fewshot-manifest "$MANIFEST" \
    ${NQ:+-n $NQ}

echo "Job completed"
date
