GPU_ID=4

# Git
SYNCBENCH_TASK='git'
GIT_START=0  # start from 0, repo_id=git_start+1
GIT_END=200

# Path
ROOT_PATH="/home/xuehangg/"
DATA_PATH="/home/xuehangg/SyncMind/source/my_repo_dict.json"

args=(--task $SYNCBENCH_TASK  --root_path $ROOT_PATH  --data_source_path $DATA_PATH 
      --git_start $GIT_START  --git_end $GIT_END)

CUDA_VISIBLE_DEVICES=$GPU_ID PYTHONDONTWRITEBYTECODE=1 python syncbench/run_syncbench.py "${args[@]}"
