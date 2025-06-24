"""
Benchmark Construction
"""

import os
import pandas as pd
from typing import List
from utils.json_util import read_test_data
from utils.logger import logger


def dataset_to_benchset(args, dataset_dict_list: List) -> pd.DataFrame:
    """Straighten dataset to instance"""
    instance_dict_list = []
    for inst_dict in dataset_dict_list:
        task_type = args.dataset
        new_instance_dict = {
            'instance_id': f"{inst_dict['repo']['repo_id']}_{inst_dict['repo']['repo_name']}_{task_type}__{inst_dict['context_data']['pyfile_name'].rstrip('.py')}__{inst_dict['fm_data']['fm_name']}__{inst_dict['changes']['commit_id']}", 
            'instance_type': task_type,
            'task_type': inst_dict['changes']['test_type'],
            'repo_url': inst_dict['repo']['repo_url'],
            'commit': inst_dict['changes']['commit_id'],
            'fm_type': inst_dict['fm_data']['fm_type'], 
            'fm_name': inst_dict['fm_data']['fm_name'], 
            'pyfile_name': inst_dict['context_data']['pyfile_name'], 
            'original_code': inst_dict['fm_data']['original_code'],
            'gold_code': inst_dict['fm_data']['gold_code'],
            'old_filtered_context': inst_dict['context_data']['old_context_code']['filtered_code'],
            'old_complete_context': inst_dict['context_data']['old_context_code']['complete_code'],
            'new_filtered_context': inst_dict['context_data']['new_context_code']['filtered_code'],
            'new_complete_context': inst_dict['context_data']['new_context_code']['complete_code'],
            'initial_error_log': inst_dict['changes']['initial_error_log'],
            'original_summary': inst_dict['changes']['original_summary'],
            'gold_summary': inst_dict['changes']['gold_summary'],
            'pyfile_path': './test_repo' + inst_dict['changes']['fm_absolute_path'].split('test_repo')[1],
            'unittest_path': './test_repo' + inst_dict['changes']['usage_test_file_path'].split('test_repo')[1]
        }
        instance_dict_list.append(new_instance_dict)
        
    instance_df = pd.DataFrame(instance_dict_list)
    return instance_df

def read_csv_to_df(file_path: str):
    """
    Read CSV file into pandas DataFrame
    
    Args:
        file_path (str): Path to CSV file
        
    Returns:
        pandas.DataFrame: DataFrame containing CSV data
    """
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    if not os.path.exists(file_path):
       open(file_path, 'w').close()
       return None
    
    if os.path.getsize(file_path) == 0:
       return None
       
    df = pd.read_csv(file_path)
    return None if df.empty else df

def save_df_to_csv(dataset: pd.DataFrame, save_path: str) -> None:
    """
    Parameters:
    - dataset (pd.DataFrame): The DataFrame dataset to be saved
    - save_path (str): The path where the CSV file will be saved.

    Returns:
    - None
    """
    directory = os.path.dirname(save_path)
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        
    try:
        dataset.to_csv(save_path, index=False, encoding='utf-8')
        logger.info(f"DataFrame successfully saved to `{save_path}` in UTF-8 encoding")
    except Exception as e:
        logger.error(f"An error occurred while saving the DataFrame: {e}")

def check_if_saved_before(existing_df, new_df):
    """Check if already saved before"""
    if existing_df is not None:
        existing_ids = set(existing_df['instance_id'])
        new_ids = set(new_df['instance_id'])
        
        if new_ids.issubset(existing_ids):
            updated_df = existing_df.copy(deep=True)
        else:
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
    
    else:
        updated_df = new_df.copy(deep=True)

    return updated_df


def syncbench_construction(args, repo_idx: int):
    """Benchmark construction"""
    dataset_name = f"{args.dataset}_{repo_idx+1}_{args.repo_source_dict_list[repo_idx]['repo_name']}"
    dataset_path = f"{args.root_path}/{args.dataset_path.replace('/', '')}/{dataset_name}.json"
    if not os.path.exists(dataset_path):
        logger.info(f"Dataset path `{dataset_path}` does not exist. Skipping instance set construction for `{dataset_name}`")
        return
    
    dataset = read_test_data(dataset_path)
    instance_df = dataset_to_benchset(args, dataset)
    inst_save_path = f"{args.root_path}/{args.syncbench_path.replace('/', '')}/{args.construct_source}/{args.dataset}_{dataset_name}.csv"
    save_df_to_csv(instance_df, inst_save_path)
    
    all_inst_save_path = f"{args.root_path}/{args.syncbench_path.replace('/', '')}/{args.construct_source}/syncbench_{args.dataset}.csv"
    existing_instance_df = read_csv_to_df(all_inst_save_path)
    updated_df = check_if_saved_before(existing_instance_df, instance_df)
    save_df_to_csv(updated_df, all_inst_save_path)
    logger.info(f"Instance set construction success for dataset `{dataset_name}`: original dataset size = {len(dataset)}  ||  instance set size = {len(instance_df)}")
    