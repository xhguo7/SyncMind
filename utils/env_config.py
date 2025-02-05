"""
Env configuration
"""

import os
import subprocess
from utils.json_util import save_to_json
from utils.default_config import default_requirements

class EnvConfig:
    def __init__(self) -> None:
        self.repo_idx = 0
        self.default_test_method = 'pytest'
        self.default_python_version = '3.11'
    
    """
    Out-of-Sync Recovery
    """
    def resync_config(self, args, repo_idx):
        self.repo_idx = repo_idx
        self.resync_code_repo_path_for_current_repo(args)
        self.repo_info_check(args)
        self.get_env_config(args)
        # self.generalized_requirements(args)
    
    def resync_code_repo_path_for_current_repo(self, args):
        if args.code_path != '/code/':
            args.code_path = '/code/'
        current_construct_dir = f"{args.code_path}{args.dataset}{self.repo_idx+1}/"
        args.code_path = current_construct_dir
        args.repo_path = current_construct_dir

    
    """
    Dataset construction configuration
    """
    # Dataset construction configuration
    def dataset_construction_config(self, args, repo_idx):
        self.repo_idx = repo_idx
        self.code_repo_path_for_current_repo(args)
        self.repo_info_check(args)
        self.get_env_config(args)
        # self.generalized_requirements(args)

    def code_repo_path_for_current_repo(self, args):
        current_construct_dir = f"{args.code_path}{args.dataset}{self.repo_idx+1}/"
        args.code_path = current_construct_dir
        args.repo_path = current_construct_dir

    # Repo information checking: must have repo_url
    def repo_info_check(self, args):
        curr_repo_info_dict = args.repo_source_dict_list[self.repo_idx]
        modify_flag = False

        # Check if missing any keys
        if len(list(curr_repo_info_dict.keys())) != 9:  # check if any is missing
            if 'github_link' not in list(curr_repo_info_dict.keys()):
                print(f"Error: No GitHub URL provided for repo-{self.repo_idx}. Please provide the corresponding GitHub URL and try again.")
                raise
            elif 'repo_id' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['repo_id'] = str(self.repo_idx + 1)  # update args
                modify_flag = True
            elif 'repo_name' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['repo_name'] = curr_repo_info_dict['github_link'].split('/')[-1]  # update args
                modify_flag = True
            elif 'test_method' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['test_method'] = self.default_test_method  # update args
                modify_flag = True
            elif 'python_version' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['python_version'] = self.default_python_version  # update args
                modify_flag = True
            elif 'requirements' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['requirements'] = []
                modify_flag = True
            elif 'install_command' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['install_command'] = []
                modify_flag = True
            elif 'additional_unittest_command' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['additional_unittest_command'] = ""
                modify_flag = True
            elif 'image_id' not in list(curr_repo_info_dict.keys()):
                args.repo_source_dict_list[self.repo_idx]['image_id'] = ""
                modify_flag = True

        # repo_url: must provide the github link of current repo
        if len(curr_repo_info_dict['github_link']) == 0:
            print(f"Error: No GitHub URL provided for repo-{self.repo_idx}. Please provide the corresponding GitHub URL and try again.")
            raise
        # repo_id = repo_idx + 1
        elif curr_repo_info_dict['repo_id'] != str(self.repo_idx + 1):
            args.repo_source_dict_list[self.repo_idx]['repo_id'] = str(self.repo_idx + 1)  # update args
            modify_flag = True
        # repo_name = github repo name
        elif len(curr_repo_info_dict['repo_name']) == 0:
            args.repo_source_dict_list[self.repo_idx]['repo_name'] = curr_repo_info_dict['github_link'].split('/')[-1]  # update args
            modify_flag = True
        # test_method = pytest/unittest
        elif (args.repo_source_dict_list[self.repo_idx]['test_method'] != 'pytest') and (args.repo_source_dict_list[self.repo_idx]['test_method'] != 'unittest'):
            args.repo_source_dict_list[self.repo_idx]['test_method'] = self.default_test_method  # update args
            modify_flag = True
        
        # Save updates
        if modify_flag:
            print(f"Successfully updated repo_source_dict_list in file `{args.repo_source_dict_list_data_path}`")
            save_to_json(args.repo_source_dict_list, args.repo_source_dict_list_data_path)  # update file

    # Env config
    def get_env_config(self, args):
        curr_repo_info_dict = args.repo_source_dict_list[self.repo_idx]

        # Test method
        if len(curr_repo_info_dict['test_method']) > 0:
            args.env_test_method = curr_repo_info_dict['test_method']
        else:
            args.env_test_method = self.default_test_method  # default test method
        
        # Python version
        if len(curr_repo_info_dict['python_version']) > 0:
            args.env_python_version = curr_repo_info_dict['python_version']
        else:
            args.env_python_version = self.default_python_version  # default python version

        # Install dependencies
        if len(curr_repo_info_dict['requirements']) == 0:
            args.env_requirements = ['pytest']
        else:
            if 'pytest' in curr_repo_info_dict['requirements']:
                args.env_requirements = curr_repo_info_dict['requirements']
            else:
                args.env_requirements = ['pytest'] + curr_repo_info_dict['requirements']
        
        # Install commands
        args.env_install_command = curr_repo_info_dict['install_command']
        
        # Additional commands
        args.env_additional_unittest_command = curr_repo_info_dict['additional_unittest_command']

        # Self-prepared env
        args.env_image_id = curr_repo_info_dict['image_id']
        if len(args.env_image_id) > 0:  # Will not remove the self-prepared docker image of current repo after completing all execution tests of current repo
            args.remove_image_after_use = False
        else:  # Will remove the docker image of current repo after completing all execution tests of current repo
            args.remove_image_after_use = True
    
    # Collect all requirements for better generalization capacity
    def generalized_requirements(self, args):
        if args.env_requirements == ['pytest']:
            for test_idx in range(len(args.repo_source_dict_list)):
                if len(args.repo_source_dict_list[test_idx]['requirements']) > 0:
                    args.env_requirements += args.repo_source_dict_list[test_idx]['requirements']
        
        # Combined with default requirements
        args.env_requirements += default_requirements
        args.env_requirements = list(set(args.env_requirements))
    


    """
    Path configuration
    """
    # Path configuration
    def path_config(self, args):
        self.directory_checker(args)
    
    # Directory checking
    def directory_checker(self, args):
        # Raise root_path error
        if not os.path.exists(args.root_path):
            print(f"[ERROR] Your defined root_path does not exists. Please check your root_path definition and try again.")

        if args.root_path.endswith('/'):
            args.root_path = os.path.join(args.root_path, 'syncbench_build')
        else:
            args.root_path = os.path.join(args.root_path, '/syncbench_build')
        
        # Check all paths
        self.create_directory(args.root_path, "root path")
        self.create_directory(f"{args.root_path}/{args.code_path.replace('/', '')}", "code path")
        self.create_directory(f"{args.root_path}/{args.dataset_path.replace('/', '')}", "data path")

        if args.task == 'downsampling':
            self.create_directory(f"{args.root_path}/{args.filtered_dataset_path.replace('/', '')}", "filtered dataset path")
            self.create_directory(f"{args.root_path}/{args.sampled_dataset_path.replace('/', '')}", "sampled dataset path")
            self.create_directory(f"{args.root_path}/{args.instance_path.replace('/', '')}", "instance path")

        if args.task == 'instantiation':
            self.create_directory(f"{args.root_path}/{args.syncbench_path.replace('/', '')}", "syncbench path")
            self.create_directory(f"{args.root_path}/{args.syncbench_path.replace('/', '')}/{args.syncbench_num}", "syncbench dataset path")

        self.create_directory(f"{args.root_path}/{args.log_path.replace('/', '')}", "log path")
        self.create_directory(f"{args.root_path}/{args.log_path.replace('/', '')}/{args.git_log_path.replace('/', '')}", "git log path")
        self.create_directory(f"{args.root_path}/{args.log_path.replace('/', '')}/{args.dataset_construction_log_path.replace('/', '')}", "dataset construction log path")
        self.create_directory(f"{args.root_path}/{args.log_path.replace('/', '')}/{args.resync_log_path.replace('/', '')}", "out-of-sync recovery log path")
        self.create_directory(f"{args.root_path}/{args.log_path.replace('/', '')}/{args.eval_log_path.replace('/', '')}", "evaluation log path")
    
    # Function to create directory if it doesn't exist
    def create_directory(self, path, description):
        if not os.path.exists(path):
            print(f"[Config Info] {description} does not exist, creating {description}: {path}")
            try:
                os.makedirs(path)
                print(f"[Config Info] Successfully created {description}: {path}")
            except OSError as e:
                raise RuntimeError(f"[Config Info] Error creating {description} at '{path}': {e}")
        else:
            print(f"[Config Validation] {description} already exists: {path}")
