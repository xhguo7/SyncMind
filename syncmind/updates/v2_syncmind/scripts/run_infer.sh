#!/bin/bash
set -eo pipefail

source "evaluation/utils/version_control.sh"

MODEL_CONFIG=$1
COMMIT_HASH=$2
AGENT=$3
EVAL_LIMIT=$4
RESYNC_METHOD=$5
REMOTE_RUNTIME=$6
MAX_ITER=$7
NUM_WORKERS=$8
TOTAL_BUDGET=${9}
CODE_COST=${10}
ASK_COST=${11}
DATA_PATH=${12}

if [ -z "$NUM_WORKERS" ]; then
  NUM_WORKERS=1
  echo "Number of workers not specified, use default $NUM_WORKERS"
fi
checkout_eval_branch

if [ -z "$AGENT" ]; then
  echo "Agent not specified, use default CodeActAgent"
  AGENT="CodeActAgent"
fi

if [ -z "$MAX_ITER" ]; then
  echo "MAX_ITER not specified, use default 30"
  MAX_ITER=30
fi

if [ -z "$USE_INSTANCE_IMAGE" ]; then
  echo "USE_INSTANCE_IMAGE not specified, use default true"
  USE_INSTANCE_IMAGE=true
fi

if [ -z "$RESYNC_METHOD" ]; then
  echo "RESYNC_METHOD not specified, use default independent"
  RESYNC_METHOD="independent"
fi

if [ -z "$REMOTE_RUNTIME" ]; then
  echo "REMOTE_RUNTIME not specified, use default False"
  REMOTE_RUNTIME="false"
fi

if [ -z "$TOTAL_BUDGET" ]; then
  echo "TOTAL_BUDGET not specified, use default \$1000"
  TOTAL_BUDGET=1000
fi

if [ -z "$CODE_COST" ]; then
  echo "CODE_COST not specified, use default \$100"
  CODE_COST=100
fi

if [ -z "$ASK_COST" ]; then
  echo "ASK_COST not specified, use default \$100"
  ASK_COST=100
fi

if [ -z "$DATA_PATH" ]; then
  echo "DATA_PATH not specified, use default: loading SyncBench from huggingface"
  DATA_PATH="None"
fi

export USE_INSTANCE_IMAGE=$USE_INSTANCE_IMAGE
echo "USE_INSTANCE_IMAGE: $USE_INSTANCE_IMAGE"

get_openhands_version

echo "AGENT: $AGENT"
echo "AGENT_VERSION: $AGENT_VERSION"
echo "MODEL_CONFIG: $MODEL_CONFIG"
echo "RESYNC_METHOD: $RESYNC_METHOD"
echo "REMOTE_RUNTIME: $REMOTE_RUNTIME"
echo "TOTAL_BUDGET: $TOTAL_BUDGET"
echo "CODE_COST: $CODE_COST"
echo "ASK_COST: $ASK_COST"
echo "DATA_PATH: $DATA_PATH"

unset SANDBOX_ENV_GITHUB_TOKEN # prevent the agent from using the github token to push

export PYTHONPATH="${PYTHONPATH}:./evaluation/benchmarks/syncmind"
# export PYTHONPATH="/shared/nas2/xuehangg/envs/poetry_venv/openhands-ai-OEMRRbiK-py3.12/lib/python3.12/site-packages"

COMMAND="PYTHONDONTWRITEBYTECODE=1 poetry run python evaluation/benchmarks/syncmind/run_infer.py \
  --agent-cls $AGENT \
  --llm-config $MODEL_CONFIG \
  --max-iterations $MAX_ITER \
  --max-chars 10000000 \
  --eval-num-workers $NUM_WORKERS \
  --resync-method $RESYNC_METHOD \
  --resync-method $RESYNC_METHOD \
  --total-budget $TOTAL_BUDGET \
  --coding-cost $CODE_COST \
  --asking-cost $ASK_COST \
  --data-path $DATA_PATH"

if [ -n "$EVAL_LIMIT" ]; then
  echo "EVAL_LIMIT: $EVAL_LIMIT"
  COMMAND="$COMMAND --eval-n-limit $EVAL_LIMIT"
fi

# Run the command
eval $COMMAND
