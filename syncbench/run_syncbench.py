"""
Main function for out-of-sync recovery configuration
"""

import ast
import argparse

import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from utils.json_util import read_test_data
from utils.env_config import EnvConfig


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    # Out-of-sync recovery config general
    parser.add_argument('--task', type=str, default='git', help='Define current task', choices=['git', 'construction', 'syncbench'])
    parser.add_argument('--dataset', type=str, default='callee', help='Dataset name: callee | caller', choices=['callee', 'caller'])
    parser.add_argument('--unittest_mode', type=str, default='fp', help='[Unit test mode] fp: fail-to-pass only | pp: pass-to-pass only | both: fail-to-pass and pass-to-pass', choices=['fp', 'pp', 'both'])
    parser.add_argument('--unittest_exetest_method', type=int, default=1, help='Execution test method for error log generation (1: sandbox | 0: local venv)', choices=[0, 1])
    parser.add_argument('--dockerhub_username', type=str, default='xuehang', help='Docker Hub user name')

    # Path
    parser.add_argument('--root_path', type=str, default='/home/xuehangg/', help='Define your root path for resync.')
    parser.add_argument('--data_source_path', type=str, default='./source/my_repo_dict.json', help='Path to your data json file for dataset construction. Please provide the whole path to your data json file.')
    
    # Git
    parser.add_argument('--git_start', type=int, default=0, help='Start index of github repo for git log downloading')
    parser.add_argument('--git_end', type=int, default=100, help='End index of github repo for git log downloading')
    
    # Dataset construction
    parser.add_argument('--max_extraction_data_length', type=int, default=1000000, help='Maximum length of extracted data to be filtered.')
    parser.add_argument('--timeout', type=int, default=600, help='Maximum timeout in seconds. Set to `600s = 10min` by default.')
    parser.add_argument('--preprocess_filter_strictness', type=int, default=0, help='If would like to implement strict function and method filtering in data preprocessing (0: general filtering | 1: strict filtering). Please be noted that selecting `1: strict filtering` may result in no collected data eventually as all candidates may be filtered out.', choices=[0, 1])
    parser.add_argument('--commit_trace_mode', type=int, default=0, help='Trace all commits for each function/method code or only the oldest commit. Noted that tracing only oldest commit will increase out-of-sync recovery task complexity. (0: all commits| 1: oldest commit only)', choices=[0, 1])
    parser.add_argument('--construct_start', type=int, default=0, help='Repo starting index for dataset construction. Max range = [0, len(repo_source_dict_list))')
    parser.add_argument('--construct_end', type=int, default=1000, help='Repo ending index for dataset construction. Max range = [0, len(repo_source_dict_list))')
    
    # Downsampling
    parser.add_argument('--filter_current_repo_only', type=int, default=1, help='[Instance Set Construction Only] If filter dataset instances for only current repo instead of all repos listed in repo_source_dict_list (0: NO | 1: YES)', choices=[0, 1])  # for instance generation only
    parser.add_argument('--repetitive_commit', type=int, default=0, help='[Instance Set Construction Only] Whether to allow different functions/methods with the same commit in sampled dataset (0: disallow so that all instances have different commits | 1: allow so that instances may have the same commit but different functions/methods)', choices=[0, 1])
    parser.add_argument('--instance_num', type=int, default=30, help='Size of instance set for both callee and caller dataset of a repository')
    parser.add_argument('--instance_start', type=int, default=0, help='Repo starting index for instance construction. Max range = [0, len(repo_source_dict_list))')
    parser.add_argument('--instance_end', type=int, default=1000, help='Repo ending index for instance construction. Max range = [0, len(repo_source_dict_list))')
    
    # SyncBench construction
    parser.add_argument('--syncbench_num', type=str, default='24k', help='Estimate the number extracted instances as the dataset subfolder name (e.g., 24k). While you are welcome to pick up any other subfolder names that you can easily remember and locate after construction.')
    
    # Pass to args
    args = parser.parse_args()

    # Dataset construction
    if args.task == 'construction':
        if args.dataset == 'callee': 
            args.task = 'construct_callee'
        else:
            args.task = 'construct_caller' 

    # Defaults
    args.dataset_path = '/dataset/'
    args.original_dataset_path = '/original_dataset/'
    args.filtered_dataset_path = '/filtered_dataset/'
    args.sampled_dataset_path = '/sampled_dataset/'
    args.instance_path = '/instance/'
    args.syncbench_path = '/syncbench/'
    args.log_path = '/log/'
    args.git_log_path = '/git_log/'
    args.dataset_construction_log_path = '/construct_log/'
    args.resync_log_path = '/resync_log/'
    args.eval_log_path = '/eval_log/'
    args.code_path = '/code/'
    args.repo_path = args.code_path
    args.repo_source_dict_list = read_test_data(args.data_source_path)
    args.env_python_version = '3.11'
    args.env_requirements = 'numpy'
    args.env_test_method = 'pytest'
    args.env_install_command = ['pip install pytest']
    args.env_additional_unittest_command = ''
    args.env_image_id = ''
    args.remove_image_after_use = False
    
    
    # Env Configuration
    env_cnfigor = EnvConfig()
    env_cnfigor.path_config(args)
    
    if args.task == 'git':
        if args.git_end > len(args.repo_source_dict_list): 
            args.git_end = len(args.repo_source_dict_list)
        if args.git_start > args.git_end:
            args.git_start = args.git_end
    
    if args.task in ['construct_callee', 'construct_caller', 'syncbench']:
        if args.construct_end > len(args.repo_source_dict_list): 
            args.construct_end = len(args.repo_source_dict_list)
        if args.construct_start > args.construct_end:
            args.construct_start = args.construct_end

    # Start SyncBench construction
    if args.task == 'git':
        args.log_dir = args.log_path + 'syncbench_%s' % (args.task)
        from syncbench.utilizer.gitloader import GitDownloader
        git_logger = GitDownloader(args)
        git_logger.git_download(args)

    elif args.task == 'construct_callee':
        args.log_dir = args.log_path + 'syncbench_%s_%s' % (args.task, args.dataset)
        from syncbench.constructor.callee import CalleeDataConstructor
        preprocessor = CalleeDataConstructor(args)
        preprocessor.all_data_construction(args)

    elif args.task == 'construct_caller':
        args.log_dir = args.log_path + 'syncbench_%s_%s' % (args.task, args.dataset)
        from syncbench.constructor.caller import CallerDataConstructor
        preprocessor = CallerDataConstructor(args)
        preprocessor.all_data_construction(args)
    
    elif args.task == 'syncbench':
        args.log_dir = args.log_path + 'data_%s' % (args.task)
        from syncbench.constructor.syncbench import syncbench_construction
        for repo_idx in range(args.construct_start, args.construct_end):
            syncbench_construction(args, repo_idx)
    
    else:
        raise ValueError('ERROR: Please set a valid task.')
    