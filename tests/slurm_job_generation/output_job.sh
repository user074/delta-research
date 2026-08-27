#!/bin/bash
#SBATCH --job-name=R007-lora-r64
#SBATCH --partition=gpu
#SBATCH --account=mylab
#SBATCH --nodes=1
#SBATCH --gpus-per-node=4
#SBATCH --cpus-per-task=32
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --output=/home/researcher/llm-finetune/RUNS/R007/slurm-%j.out

cd /home/researcher/llm-finetune
set -euo pipefail

module load cuda/12.2 anaconda3
source /opt/conda/etc/profile.d/conda.sh
conda activate /opt/conda/envs/llm-ft

export WANDB_PROJECT=llm-finetune
export WANDB_MODE=offline
export WANDB_RUN_NAME=R007
export WANDB_DIR=/home/researcher/llm-finetune/RUNS/R007/wandb
export HF_HOME=/scratch/researcher/.cache/huggingface

if ! torchrun --standalone --nproc_per_node=4 /home/researcher/llm-finetune/RUNS/R007/experiment.py; then
  echo "[DELTA-BLOCKER] R007 | hero torchrun failed on at least one rank"
  exit 1
fi
