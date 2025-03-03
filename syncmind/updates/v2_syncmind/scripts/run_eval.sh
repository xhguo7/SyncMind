#!/bin/bash
set -eo pipefail

source "evaluation/utils/version_control.sh"

EVAL_PATH=$1

if [ -z "$EVAL_PATH" ]; then
  echo "EVAL_PATH not specified"
  DATA_PATH="path-to-result"
fi

echo "EVAL_PATH: $EVAL_PATH"

COMMAND="PYTHONDONTWRITEBYTECODE=1 poetry run python evaluation/benchmarks/syncmind/run_eval.py \
  --eval_path $EVAL_PATH"

# Run the command
eval $COMMAND
