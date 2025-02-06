GPU_ID=4

# Path
ROOT_PATH="/home/xuehangg/"
DATA_PATH="/home/xuehangg/SyncMind/source/my_repo_dict.json"

# Dataset Construction
SYNCBENCH_TASK="construction"
DATASET="caller"  # callee | caller
ET_SANDBOX=1
STRICT_FILTERING=0  # 0: not strict | 1: strict (may result in no filtered data being collected)
TIMEOUT=600
MAX_LENGTH=1000000

# [CONSTRUCT_START, CONSTRUCT_END), start from 0
CONSTRUCT_START=0
CONSTRUCT_END=1

# Unit test
TEST_MODE="fp"
TRACE_MODE=0

# Docker
USER_NAME="xuehang"

args=(--task $SYNCBENCH_TASK  --root_path $ROOT_PATH  --data_source_path $DATA_PATH  --dataset $DATASET  
      --unittest_exetest_method $ET_SANDBOX  --unittest_mode $TEST_MODE  --commit_trace_mode $TRACE_MODE
      --construct_start $CONSTRUCT_START  --construct_end $CONSTRUCT_END  --max_extraction_data_length $MAX_LENGTH
      --timeout $TIMEOUT  --preprocess_filter_strictness $STRICT_FILTERING  --dockerhub_username $USER_NAME)

CUDA_VISIBLE_DEVICES=$GPU_ID PYTHONDONTWRITEBYTECODE=1 python syncbench/run_syncbench.py "${args[@]}"
