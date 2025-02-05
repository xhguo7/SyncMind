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
DATA_PATH=$9

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

if [ -z "$DATA_PATH" ]; then
  echo "DATA_PATH not specified, use default ./data/instance_example.csv"
  DATA_PATH="None"
fi

export USE_INSTANCE_IMAGE=$USE_INSTANCE_IMAGE
echo "USE_INSTANCE_IMAGE: $USE_INSTANCE_IMAGE"

get_agent_version

echo "AGENT: $AGENT"
echo "AGENT_VERSION: $AGENT_VERSION"
echo "MODEL_CONFIG: $MODEL_CONFIG"
echo "RESYNC_METHOD: $RESYNC_METHOD"
echo "REMOTE_RUNTIME: $REMOTE_RUNTIME"
echo "DATA_PATH: $DATA_PATH"

unset SANDBOX_ENV_GITHUB_TOKEN # prevent the agent from using the github token to push

export PYTHONPATH="${PYTHONPATH}:./syncmind/framework/OpenHands"

COMMAND="PYTHONDONTWRITEBYTECODE=1 poetry run python evaluation/syncmind/run_infer.py \
  --agent-cls $AGENT \
  --llm-config $MODEL_CONFIG \
  --max-iterations $MAX_ITER \
  --max-chars 10000000 \
  --eval-num-workers $NUM_WORKERS \
  --resync-method $RESYNC_METHOD \
  --remote-runtime $REMOTE_RUNTIME \
  --data-path $DATA_PATH"

if [ -n "$EVAL_LIMIT" ]; then
  echo "EVAL_LIMIT: $EVAL_LIMIT"
  COMMAND="$COMMAND --eval-n-limit $EVAL_LIMIT"
fi

# Run the command
eval $COMMAND
