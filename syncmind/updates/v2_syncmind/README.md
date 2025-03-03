# Evaluation on *SyncBench*

## 1. Run Inference
Please make sure that you have put this directory under `OpenHands/evaluation/benchmarks/syncmind`.

Then:
```
cd OpenHands
```

### 1.1 Agent Out-of-Sync Recovery
- Run agent out-of-sync recovery:
    ```
    bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh [llm configuration] [git version] [agent] [evaluation limit] [out-of-sync recovery method] [if using remote run] [max-turn limit] [num-workers] [evaluation data path]
    ```

- For example: 
    - Run *SyncMind* with `GPT-4o` as the agent tackling out-of-sync
        - `[llm configuration]`: llm.gpt_4o 
        - `[git version]`: HEAD 
        - `[agent]`: CodeActAgent
        - `[evaluation limit]`: 10
        - `[out-of-sync recovery method]`: independent
        - `[if using remote run]`: false
        - `[max-turn limit]`: 30
        - `[num-workers]`: 1
        - `[evaluation data path]`: set this field only if you have downloaded *SyncBench* locally

            - If loading *SyncBench* directly from Hugging Face, skip `[evaluation data path]`:
                ```
                bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 10 independent false 30 1
                ```

            - Or have already downloaded SyncBench locally: 
                Run *SyncMind* on local dataset `./data/callee_11_whisper_instance.csv`:
                ```
                bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 10 independent false 30 1 ./data/callee_11_whisper_instance.csv 
                ```

### 1.2 Resource-Aware Agent Out-of-Sync Recovery
- Run resource-aware agent out-of-sync recovery:
    ```
    bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh [llm configuration] [git version] [agent] [evaluation limit] [out-of-sync recovery method] [if using remote run] [max-turn limit] [num-workers] [evaluation data path] [resource-budget] [resource-coding cost] [resource-asking cost]
    ```

- For example:
    - Resource-aware agent out-of-sync recovery:
        - `[max-turn limit]`: 30
        - `[resource-budget]`: 1000 (default)
        - `[resource-coding cost]`: 100 (default)
        - `[resource-asking cost]`: 100 (default)

    - If would like to define a different setting of resources
        - `[max-turn limit]`: 20
        - `[resource-budget]`: 3000
        - `[resource-coding cost]`: 50
        - `[resource-asking cost]`: 200

            - If loading *SyncBench* directly from Hugging Face, skip `[evaluation data path]`:
                ```
                bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 10 independent false 20 1 3000 50 200
                ```

            - Or have already downloaded SyncBench locally: 
                Run *SyncMind* on local dataset `./data/callee_11_whisper_instance.csv`:
                ```
                bash ./evaluation/benchmarks/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 10 independent false 20 1 3000 50 200 ./data/callee_11_whisper_instance.csv
                ```


## 2. Run Evaluation
- Results of agent out-of-sync will be automatically saved to `OpenHands/evaluation/benchmarks/syncmind/tmps`
- Run evaluation on agent out-of-sync results
    - `[path to eval data]`: replace this with the actual path of the results you woule like to evaluate
        ```
        cd OpenHands
        bash ./evaluation/benchmarks/syncmind/scripts/run_eval.sh [path to eval data]
        ```
        The evaluation result will be saved to *the same directory* as your eval data, with the file name `eval_summary_{timestamp}.json`.
