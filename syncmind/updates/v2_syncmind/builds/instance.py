"""
Instance processing functions
"""

import os
import shutil
import subprocess
import psutil
import time
import pandas as pd
from openhands.core.logger import openhands_logger as logger
from evaluation.benchmarks.syncmind.builds.loader import DockerHandler
from evaluation.benchmarks.syncmind.builds.aligner import align_agent_context


class InstanceProcessor:
    """Process instance"""
    def __init__(self, instance: pd.Series) -> None:
        """InstanceProcessor init"""

        # TODO: Repo clone method: online | local
        '''
        "online": clone from online GitHub repo
        "local": clone from local docker image
        '''
        self.clone_method = "local"  # online | local

        # TODO: Temp dir creation option
        '''
        "force": force creation; will remove original if already exists
        "efficient": will use current tmp_dir if already exists, instead of removing tmp_dir and recreating
        '''
        self.tmp_dir_creation_option = "efficient"  # force | efficient

        # Instance
        self.instance = instance
        self.instance_id = instance.instance_id
        self.repo_url = instance.repo_url
        self.original_code = instance.original_code
        self.pyfile_name = instance.pyfile_name
        self.pyfile_path = instance.pyfile_path
        self.context_code = instance.new_complete_context

        # Instance paths
        self.agent_workdir = '/workspace/test_repo'
        self.local_tmp_dir = f'tmps/{self.instance_id}'
        self.local_code_dir_path = None
        self.repo_dir = None
        self.context_code_path = None        
        self.path_init()

    
    def path_init(self):
        """Init paths"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dir_name = os.path.dirname(os.path.abspath(__file__)).split('/')[-1]
        self.local_code_dir_path = current_dir.replace(dir_name, self.local_tmp_dir)
        self.tmp_dir_creation(self.local_code_dir_path)
        self.repo_dir = os.path.join(self.local_code_dir_path, 'test_repo')
        self.context_code_path = f"{self.repo_dir.split('test_repo')[0] + 'test_repo' + self.pyfile_path.split('test_repo')[1]}"
    
    def tmp_dir_creation(self, tmp_dir):
        """
        Function:
        - Create temporary directory

        TODO: self.tmp_dir_creation_option
        - "force": force creation; will remove original if already exists
        - "efficient": will use current tmp_dir if already exists, instead of removing tmp_dir and recreating
        """
        retries, delay = 15, 5

        if self.tmp_dir_creation_option == "force":
            self.tmp_dir_creation_force(tmp_dir)
        else:
            if os.path.exists(tmp_dir):
                logger.info(f"Directory already exists at `{tmp_dir}`. Skipping directory creation...")
                return
        
        for attempt in range(retries):
            try:
                logger.info(f"Creating new temporary directory at `{tmp_dir}`...")
                os.makedirs(tmp_dir, exist_ok=True)
                logger.info(f"Successfully created temporary local directory: {tmp_dir}")
                break
            except FileExistsError as e:
                if attempt < retries - 1:
                    logger.warning(f"Directory `{tmp_dir}` was created by another process (attempt {attempt+1}/{retries}). Retrying after {delay} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"Failed to create `{tmp_dir}` after {retries} attempts. Error: {e}")
                    raise  # Re-raise if unable to create after all attempts
            
    
    def tmp_dir_creation_force(self, tmp_dir):
        """Create temporary directory"""
        retries, delay = 15, 5
        
        if os.path.exists(tmp_dir):
            logger.info(f"Directory already exists at `{tmp_dir}`. Attempting to remove existing directory...")

            for attempt in range(retries):
                try:
                    if self.is_dir_in_use(tmp_dir):
                        logger.warning(f"Directory `{tmp_dir}` is in use by another process. Retrying...")
                        time.sleep(delay)
                        continue
                    
                    shutil.rmtree(tmp_dir)
                    logger.info(f"Successfully removed existing directory: {tmp_dir}")
                    break

                except Exception as e:
                    if attempt < retries - 1:
                        logger.warning(f"Failed to remove `{tmp_dir}` (attempt {attempt+1}/{retries}). "
                                       f"Error: {e}. Retrying in {delay} seconds...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Failed to remove `{tmp_dir}` after {retries} attempts. Error: {e}")
                        raise  # Re-raise the exception after final attempt
    
    def is_dir_in_use(self, dir_path):
        """Check if is already in use by another process"""
        for proc in psutil.process_iter(['pid', 'name', 'open_files']):
            try:
                for file in proc.info['open_files'] or []:
                    if file.path.startswith(dir_path):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False
    
    def remove_tmp_dir(self, tmp_dir):
        """Remove temporary directory"""
        if os.path.exists(tmp_dir):
            subprocess.run(['rm', '-rf', tmp_dir])
            logger.info(f"Successfully removed directory: {tmp_dir}")
        else:
            logger.info(f"Directory does not exist: {tmp_dir}")

    def instance_tmp_clean_up(self):
        """Clean up"""
        self.remove_tmp_dir(self.local_code_dir_path)

    def clone_repo(self):
        """Clone GitHub repository for current instance"""
        if not os.path.exists(self.repo_dir):
            try:
                subprocess.run(["git", "clone", self.repo_url, self.repo_dir], check=True)
                logger.info(f"Repository cloned to `{self.repo_dir}`")
            except subprocess.CalledProcessError as e:
                logger.info(f"Failed to clone repository: {e}")
        else:
            logger.info(f"Repository already exists at `{self.repo_dir}`")
    
    def clone_repo_from_image(self):
        """Clone GitHub repo for current instance from docker image"""
        if not os.path.exists(self.repo_dir):
            try:
                docker_handler = DockerHandler(self.instance, self.context_code_path, "/workspace/test_repo")
                docker_handler.all_in_one_run_copy_remove_container()
                logger.info(f"Repository cloned from docker image to `{self.repo_dir}`")
            except subprocess.CalledProcessError as e:
                logger.info(f"Failed to clone repository from docker image: {e}")
        else:
            logger.info(f"Repository already exists at `{self.repo_dir}`")
    
    def read_context_code(self, context_path: str) -> str:
        """Read context code"""
        if os.path.exists(context_path):
            with open(context_path, 'r') as file:
                context_code = file.read()
                logger.info(f"Reading context code from {context_path}")
                return context_code
        else:
            raise FileNotFoundError(f"Context code not found: {context_path}")
    
    def ensure_agent_code_path_exists(self, code_path):
        """Ensure code path exists before reading/writing operation"""
        if not os.path.exists(code_path):
            if code_path.endswith('/'):
                os.makedirs(code_path)
                logger.info(f"Directory created at: {code_path}")
            else:
                os.makedirs(os.path.dirname(code_path), exist_ok=True)
                logger.info(f"File created at: {code_path}")
        else:
            logger.info(f"Passed code checking: code path exists at `{code_path}`")
        
    def save_context_code(self, restored_context_code: str, context_path: str) -> None:
        """Save context code"""
        self.ensure_agent_code_path_exists(context_path)
        with open(context_path, 'w') as file:
            file.write(restored_context_code)
        logger.info(f"Restored context code successfully saved to {context_path}")
    
    def prepare_history_code(self):
        """Prepare history code for out-of-sync recovery"""
        if self.clone_method == "online":
            self.clone_repo()  # from GitHub repo
        else:
            self.clone_repo_from_image()  # from docker image
        restored_code = align_agent_context(self.original_code, self.context_code)
        self.save_context_code(restored_code, self.context_code_path)
        
    def instance_restoration(self):
        """Prepare instance code"""
        self.prepare_history_code()
        local_file_path = self.context_code_path
        target_image_path = self.agent_workdir + self.context_code_path.split('test_repo')[1]
        target_image_dir = target_image_path.replace(f"/{self.pyfile_name}", "")
        return local_file_path, target_image_dir, target_image_path
    