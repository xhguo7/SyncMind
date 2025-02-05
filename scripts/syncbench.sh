GPU_ID=4

# Path
ROOT_PATH="/home/xuehangg/"
DATA_PATH="/home/xuehangg/SyncMind/source/my_repo_dict.json"

# Dataset Construction
SYNCBENCH_TASK='syncbench'
DATASET='caller'  # caller | callee

# Source data
CONSTRUCT_START=0
CONSTRUCT_END=22

args=(--task $SYNCBENCH_TASK  --dataset $DATASET  
      --root_path $ROOT_PATH  --data_source_path $DATA_PATH
      --construct_start $CONSTRUCT_START  --construct_end $CONSTRUCT_END)

CUDA_VISIBLE_DEVICES=$GPU_ID PYTHONDONTWRITEBYTECODE=1 python syncbench/run_syncbench.py "${args[@]}"
