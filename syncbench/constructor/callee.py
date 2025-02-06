"""
Callee Construction
"""
import json
from syncbench.constructor.callee_builder import CalleeConstructor
from utils.env_config import EnvConfig

class CalleeDataConstructor(object):
    def __init__(self, args):
        """Init Caller constructor"""
        self.data_len = len(args.repo_source_dict_list)
        self.all_fm_list = []
        self.dataset_save_path = f"{args.root_path}{args.dataset_path}"
    
    def save_to_json(self, data, save_path):
        """Save data to JSON"""
        with open(save_path, 'w') as data_file:
            json.dump(data, data_file, indent=4)
    
    # Construct all repos listed in args.repo_source_dict_list, with git log filtering
    def all_data_construction(self, args):
        """Generate dataset for a range of source repositories"""
        for repo_idx in range(args.construct_start, args.construct_end):
            # Env configuration
            env_configor = EnvConfig()
            env_configor.dataset_construction_config(args, repo_idx)
            
            # Dataset construction
            curr_repo_info_dict = args.repo_source_dict_list[repo_idx]
            curr_repo_id = curr_repo_info_dict['repo_id']
            args.env_python_version = curr_repo_info_dict['python_version']
            benchmark = CalleeConstructor(args, curr_repo_id)
            
            filtered_fm_fict_list = benchmark.extract_fm_from_in_test_object(args, benchmark.clone_dir)
            self.all_fm_list += filtered_fm_fict_list
        
        args.task = 'syncbench'
        self.syncbench_instantiation(args)
        
    # Construct each repo given its repo_id, with git log filtering
    def single_repo_data_construction(self, args, repo_id):
        """Generate dataset for a single source repository"""
        # Env configuration
        env_configor = EnvConfig()
        env_configor.dataset_construction_config(args, repo_id-1)
        
        # Dataset construction
        args.env_python_version = args.repo_source_dict_list[repo_id-1]['python_version']
        benchmark = CalleeConstructor(args, repo_id)
        
        filtered_fm_dict_list = benchmark.extract_fm_from_in_test_object(args, benchmark.clone_dir)
        self.save_to_json(filtered_fm_dict_list, f"{self.dataset_save_path}callee_{self.repo_id}_{self.repo_name}.json")

        args.task = 'syncbench'
        self.syncbench_instantiation(args)
        
        return filtered_fm_dict_list
    
    def syncbench_instantiation(self, args):
        """Construct SyncBench with instantiated datasets"""
        args.log_dir = args.log_path + 'data_%s' % (args.task)
        from syncbench.constructor.syncbench import syncbench_construction
        for repo_idx in range(args.construct_start, args.construct_end):
            syncbench_construction(args, repo_idx)
