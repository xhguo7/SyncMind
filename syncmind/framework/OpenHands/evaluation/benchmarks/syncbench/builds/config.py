"""
Agent out-of-sync recovery config
"""

import os
import shutil
from pandas import Series
from openhands.core.logger import openhands_logger as logger

class SyncMindConfig:
    def __init__(
            self
        ) -> None:
        # Agent
        self.agent_model = None

        # Instance
        self.instance_dataset_path = None
        self.instance_set_name = None

        # Default: data path and output path
        self.resync_data_source_path = os.path.dirname(os.path.abspath(__file__)).split('syncmind')[0] + "syncmind/data/my_repo_dict.json"
        self.save_dir_name = f"output_dir"
        self.resync_output_save_dir = os.path.dirname(os.path.abspath(__file__)).split('syncmind')[0] + f"syncmind/tmps/syncmind_outputs/{self.save_dir_name}/"
        self.resync_temp_save_dir = os.path.dirname(os.path.abspath(__file__)).split('syncmind')[0] + f"syncmind/tmps/"
    
    def init_instance_path(
            self, 
            instance_dataset_path: str, 
            resync_method: str, 
            RESOURCE_AWARENESS: dict, 
            max_iterations: int, 
            agent_model: str
        ) -> None:
        # Agent
        self.agent_model = agent_model.replace("llm.", "")
        # Instance
        self.instance_dataset_path = instance_dataset_path

        # Update: output path
        self.instance_set_name = instance_dataset_path.split(f"/")[-1].replace("_instance.csv", "")
        if resync_method == 'independent':
            self.save_dir_name = f"{self.instance_set_name}_{resync_method}_budget{RESOURCE_AWARENESS['total_budget']}_code{RESOURCE_AWARENESS['coding_cost']}_max{max_iterations}turn_{self.agent_model}"
        else:
            self.save_dir_name = f"{self.instance_set_name}_{resync_method}_budget{RESOURCE_AWARENESS['total_budget']}_code{RESOURCE_AWARENESS['coding_cost']}_ask{RESOURCE_AWARENESS['asking_cost']}_max{max_iterations}turn_{self.agent_model}"
        self.resync_output_save_dir = os.path.dirname(os.path.abspath(__file__)).split('syncmind')[0] + f"syncmind/tmps/syncmind_{self.agent_model}_max{max_iterations}turn_budget{RESOURCE_AWARENESS['total_budget']}_code{RESOURCE_AWARENESS['coding_cost']}_ask{RESOURCE_AWARENESS['asking_cost']}/{self.save_dir_name}/"
        
    def check_create_dir(self, dir_path: str):
        """
        Checks if the directory at `dir_path` exists. 
        If it exists, deletes the existing directory and recreates it.
        If it does not exist, creates the directory.

        :param dir_path: The path of the directory to be checked and created.
        """
        if os.path.exists(dir_path):
            logger.info(f"Directory already exists at `{self.resync_output_save_dir}`\nRemoving existing dir and recreating a new one...")
            shutil.rmtree(dir_path)
            logger.info(f"Successfully removed existing directory at `{self.resync_output_save_dir}`")
    
        os.makedirs(dir_path, exist_ok=True)
        logger.info(f"Successfully created directory at `{self.resync_output_save_dir}`")
    
    def remove_tmp_dir(self):
        """
        Removes the specified temporary directory `tmp_dir` and all its contents.

        If the directory exists, it deletes the directory along with all files and subdirectories within it.
        If the directory does not exist, a log message will indicate that no action is needed.
    
        :param tmp_dir: The path of the temporary directory to be removed.
        """
        tmp_dir = self.resync_temp_save_dir

        if os.path.exists(tmp_dir):
            logger.info(f"Temporary directory exists at `{tmp_dir}`. Removing the directory and its contents...")

            try:
                shutil.rmtree(tmp_dir)
                logger.info(f"Successfully removed the temporary directory at `{tmp_dir}`.")
        
            except Exception as e:
                logger.exception(f"Failed to remove the directory `{tmp_dir}`: {e}\nYou may want to remove it manually after evaluation: your_tmp_dir=`{tmp_dir}`")
    
        else:
            logger.info(f"Directory `{tmp_dir}` does not exist. No removal necessary.")
