# **SyncBench:** Agent Out-of-Sync Benchmark


## **[SyncBench](https://github.com/xhguo7/SyncMind/blob/main/syncbench/SyncBench.md)**
<p align="center">
  <img src="../assets/syncbench.png" width="800" alt="Alt text">
</p>


## 🍀**1. Environment Setup**

To use **SyncMind** and **SyncBench**:
```
git clone https://github.com/xhguo7/SyncMind.git
```

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



## 📝 **2. Dataset Construction**

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

  - Define function and method filtering strictness
    ```
    STRICT_FILTERING=0  # 0: not strict | 1: strict (may result in no filtered data being collected)
    ```

    If set `STRICT_FILTERING=1`, what will be filtered out?
    - Filter out functions with zero arguments
    - Filter out functions with no return statements
    - Filter out functions with literal return values
    - Filter out functions without a docstring
    - Filter out functions with bad names (e.g., "test", "temp", or "sample")
    - Filter out functions that are 5 lines or shorter
    - Filter out functions with syntax errors in the code
    - Filters out dunder functions (e.g., functions starting with '__')

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

**(2) (Optional) Check Gits**
  - If would like to check git commits before constructing *SyncBench*
    ```
    cd SyncMind
    bash ./scripts/git.sh
    ```

**(3) SyncBench Construction**
  - Construct *SyncBench*
    ```
    cd SyncMind
    bash ./scripts/construction.sh
    ```
    This will save both the structured data in `.json` format and the instantiated data in `.csv` format
    - `JSON` data: will be saved to `./syncbench_build/dataset` in `.json` format
    - `CSV` data: will be saved to `./syncbench_build/syncbench` in `.csv` format

    Where `syncbench_build` shares the same parent directory as `SyncMind`.

**(4) (Optional) SyncBench Instantiation**
  - Want to customize instances? Run `syncbench.sh`:
    - To instantiate `JSON` data into `CSV` instances (after running syncbench construction `bash ./scripts/construction.sh` to generate `JSON` data):
      ```
      cd SyncMind
      bash ./scripts/syncbench.sh
      ```
      This will convert structured `.json` data into instantiated datasets in `.csv` format
      - `CSV` data: will be saved to `./syncbench_build/syncbench` in `.csv` format

      Where `syncbench_build` shares the same parent directory as `SyncMind`.
  - Noted that this step in totally optional, just in case if you would like to change instance attributes.
    - Running `construction.sh` already includes this instantiation step with default attributes for agent out-of-sync recovery evaluation.


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

#### **3.1.2 Let's Expand SyncBench!**
**(1) (Optional) Check gits**
```
cd SyncMind
bash ./scripts/git.sh
```

**(2) Construct datasets**
```
cd SyncMind
bash ./scripts/construction.sh
```
This will save the constructed datasets in `.json` format

**(3) (Optional) Instantiate SyncBench for Agent Out-of-Sync Recovery**
```
cd SyncMind
bash ./scripts/syncbench.sh
```
This will save the constructed datasets in `.csv` format



### 📉 **3.2 Scale Down**
For small-scale evaluation, **SyncBench** can be readily downsampled to fewer instances:

**(1) 300 Instances:**
  - We have sampled a small evaluation dataset through weighted downsampling: [300 Instances](https://huggingface.co/datasets/xuehang/SyncBench)
    - 300 out-of-sync instances derived from 21 GitHub repositories
      - 150 Caller instances
      - 150 Callee instances

**(2) Custom subset**
  - Choose a proper method to downsample a custom *SyncBench* subset
