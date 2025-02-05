<h1 align="center"><b> SyncMind: Agent Out-of-Sync Recovery in Collaborative Software Engineering </b></h1>

<p align="center">
<a href="https://https://xhguo7.github.io/SyncMind">🌐 Homepage</a>
•
<a href="https://xhguo7.github.io/SyncMind">📃 Paper</a>
•
<a href="https://huggingface.co/datasets/xuehang/SyncBench" >🤗 Data</a>
•
<a href="https://github.com/xhguo7/SyncMind" >🗂️ Code</a>
</p>


## **SyncMind**
<p align="center">
  <img src="assets/syncmind.png" width="800" alt="Alt text">
</p>

## **SyncBench**
<p align="center">
  <img src="assets/syncbench.png" width="800" alt="Alt text">
</p>



## 🍀**1. Environment Setup**

To use **SyncMind** and **SyncBench** for *agent out-of-sync recovery*:
```
git clone https://github.com/xhguo7/SyncMind.git
```

### **1.1 SyncMind**
Setup environment for **SyncMind**:
- We are using [OpenHands](https://github.com/All-Hands-AI/OpenHands) to implement interactive codebase environments for agent *out-of-sync* recovery.
  - Miniconda env setup: may refer to [Development.md](https://github.com/All-Hands-AI/OpenHands/blob/main/Development.md) for further details
    ```
    # Download and install Mamba (a faster version of conda)
    curl -L -O "https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-$(uname)-$(uname -m).sh"
    bash Miniforge3-$(uname)-$(uname -m).sh

    # Install Python 3.12, nodejs, and poetry
    mamba install python=3.12
    mamba install conda-forge::nodejs
    mamba install conda-forge::poetry
    ```

- Our experiments in paper are conducted on [OpenHands `0.10.0`](https://github.com/xhguo7/OpenHands12) 
  - Can directly use **SyncMind** on [OpenHands `0.10.0`](https://github.com/xhguo7/OpenHands12):
    - *Quick Use*: May directly use the entire framework
      ```
      cd SyncMind/syncmind/framework/OpenHands
      ```
    - *OR*: May clone [OpenHands `0.10.0`](https://github.com/xhguo7/OpenHands12) to your desired local path
      ```
      git clone https://github.com/xhguo7/OpenHands12.git
      cp -rp SyncMind/syncmind/framework/syncmind OpenHands12/evaluation/
      ```
  - Can also leverage our updated **SyncMind** on latest [OpenHands](https://github.com/All-Hands-AI/OpenHands)
    - We will do our best to maintain the synchronized version of **SyncMind** that can be compatible with the latest [OpenHands](https://github.com/All-Hands-AI/OpenHands)
    - Check our recent updates at [SyncMind.md](https://github.com/xhguo7/SyncMind/blob/main/syncmind/SyncMind.md)
    - We will save updated versions of **SyncMind** to the following directory:
    ```
    cd SyncMind/syncmind/updates/syncmind
    ```



### **1.2 SyncBench**

- **Quick Install:**
  ```
  conda env create -f environment.yml
  conda activate syncmind
  ```

- **Env Setup:**
  ```
  cd your_desired_root_dir
  git clone https://github.com/xhguo7/SyncMind.git
  cd SyncMind
  python -m pip install -e .
  ```



## 🚀**2. Quick Start**

### **2.1 SyncMind: Agent Out-of-Sync Recovery Evaluation**
- Prepare data
  - *SyncBench*
    - In our current version, [SyncBench](https://huggingface.co/datasets/xuehang/SyncBench) is built upon 21 popular GitHub repositories.
    - For computational efficiency, we also downsampled an evaluation subset comprising [300 instances](https://huggingface.co/datasets/xuehang/SyncBench) for agent *out-of-sync* evaluation.

- Run *SyncMind*
  ```
  cd SyncMind/syncmind/framework/OpenHands
  bash ./evaluation/syncmind/scripts/run_infer.sh [llm configuration] [git version] [agent] [evaluation limit] [out-of-sync recovery method] [evaluation data path] [if using remote run] [max-turn limit] [num-workers]
  ```

  For example: run *SyncMind* for `GPT-4o` on `callee_11_whisper_instance.csv`:
  ```
  bash ./evaluation/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 100 independent false 30 1 ./data/callee_11_whisper_instance.csv 
  ```
  Or loading SyncBench directly from Hugging Face:
  ```
  bash ./evaluation/syncmind/scripts/run_infer.sh llm.gpt_4o HEAD CodeActAgent 100 independent false 30 1
  ```

- Metrics
  ```
  cd ./SyncMind/syncmind/framework/OpenHands/evaluation/syncmind/metrics/
  python run_eval.py
  ```

### **2.2 SyncBench: Agent Out-of-Sync Recovery Benchmark Construction**

**(1) Load SyncBench**
```
from datasets import load_dataset
dataset = load_dataset("xuehang/SyncBench")
```

**You can now access all SyncBench datasets:**
- Evaluation dataset consisting of 300 instances: `dataset['syncbench_300']`
  - Callee: `dataset['syncbench_callee_150']`
  - Caller: `dataset['syncbench_caller_150']`
- SyncBench consisting of 24,332 instances: `dataset['syncbench_24k']`
  - Callee: `dataset['syncbench_24k_callee']`
  - Caller: `dataset['syncbench_24k_caller']`

**(2) Load A Specific SyncBench Dataset**
```
from datasets import load_dataset
dataset = load_dataset("xuehang/SyncBench", data_files=<dataset_name>)
```

**Fill in `<dataset_name>` with a specific dataset name:**
- syncbench_300
  - syncbench_callee_150
  - syncbench_caller_150
- syncbench_24k
  - syncbench_24k_callee
  - syncbench_24k_caller

For example:
```
from datasets import load_dataset
dataset = load_dataset("xuehang/SyncBench", data_files="syncbench_300.csv")
```


### **2.3 Unit Test**
Run unit test:
  ```
  cd SyncMind
  pytest ./tests/test_syncbench.py -v
  ```


## 🎨**3. Customize Your SyncBench**

In our current version, [SyncBench](https://huggingface.co/datasets/xuehang/SyncBench) is built upon 21 popular GitHub repositories.

**SyncBench** can be readily scale up by applying to diverse qualified Python repositories, and can also be quickly downsampled to smaller evaluation subsets.

### 📈 **3.1 Scale Up**
**SyncBench** can be readily scale up by applying to diverse Python repositories that meet the following prerequisites:
  - Have *Python* as the primary language
  - Possess well-developed unit tests
  - (Optional) Support easy *env setup* is a plus, be not required
    - Repositories with *env setup* files, such as `setup.py`, `.toml`, `.yml`, etc., can help quickly build up the docker environment
    - Meanwhile, please be rest assured that you can also manually specified certain packages to install when your selected repositories may not include these *env setup* files.

#### **3.1.1 Prepare Source Repo**

**Source Repository**

Edit source repo at: `./source/my_repo_dict.json`
- Append new source repositories to this dictionary
- One may preset environment dependencies in this dictionary if the source repository does not prepare environment setup necessities

Set source repo in *SyncBench* construction command to specify which source repositories to use.

#### **3.1.2 Configuration**
**(1) Set params**
  ```
  cd SyncMind/scripts/construction.sh
  ```
  - Set `root_path` to the dir with enough space to save generated benchmark instances
    ```
    ROOT_PATH="/home/xuehangg/"
    ```

  - Set the path to source repositories
    ```
    DATA_PATH="./source/my_repo_dict.json"
    ```

  - Set dataset type: `caller` or `callee`
    ```
    DATASET='caller'
    ```

  - Define function and method filtering strictness (See more filtering details at [SyncBench.md](https://github.com/xhguo7/SyncMind/blob/main/syncbench/SyncBench.md))
    ```
    STRICT_FILTERING=0  # 0: not strict | 1: strict (may result in no filtered data being collected)
    ```

  - Define execution test timeout
    ```
    TIMEOUT=600
    ```

  - Define the maximum length of data to be filtered
    ```
    MAX_LENGTH=1000
    ```

  - Set source repository range: `[CONSTRUCT_START, CONSTRUCT_END), start from 0`
    
    For example, if constructing SyncBench based on source repositories with ID `1-3`:
    ```
    CONSTRUCT_START=0
    CONSTRUCT_END=3
    ```

  - Set out-of-sync mode

    [Execution test filtering mode]
    - `fp`: fail-to-pass only
    - `pp`: pass-to-pass only
    - `both`: fail-to-pass and pass-to-pass
    ```
    TEST_MODE="fp"
    ```

  - Set commit tracing mode

    - Trace all commits that satisfy `TEST_MODE`: `TRACE_MODE=0`
    - Trace only the oldest commit that satisfies `TEST_MODE`: `TRACE_MODE=0`
    ```
    TRACE_MODE=0
    ```

#### **3.1.3 Let's Expand SyncBench!**
**(1) (Optional) Check gits**
```
cd SyncMind
bash ./scripts/git.sh
```

**(2) Run construction**
```
cd SyncMind
bash ./scripts/construction.sh
```
This will save the constructed datasets in `.json` format

**(3) Build SyncBench**
```
cd SyncMind
bash ./scripts/syncbench.sh
```
This will save the instantiated datasets in `.csv` format


### 📉 **3.2 Scale Down**
For small-scale evaluation, **SyncBench** can be readily downsampled to fewer instances:

**(1) 300 Instances:**
  - We have sampled a small evaluation dataset through weighted downsampling: [300 Instances](https://huggingface.co/datasets/xuehang/SyncBench)

**(2) Custom subset**
  - Choose a proper method to downsample a custom *SyncBench* subset
