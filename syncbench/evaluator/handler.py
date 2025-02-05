"""
Download the folder from a docker image to local host
"""

import os
import time
import subprocess
from utils.logger import logger


class DockerHandler:
    def __init__(self, image_name_with_tag: str, local_file_path: str):
        self.image_name_with_tag = image_name_with_tag
        self.container_path = '/workspace/test_repo'
        self.container_name = f'{image_name_with_tag.replace('/', '_').replace(':', '_')}' + "__" + str(time.asctime()).replace(" ", "__").replace(":", "_") + f"__{self.container_path.split('/')[-1]}__dockerhandler"
        self.local_path = local_file_path
        self.ensure_path_exists(self.local_path)

    def ensure_path_exists(self, dir_path):
        """Check if the path already exists"""
        if os.path.exists(dir_path):
            logger.info(f"The local path '{dir_path}' already exists.")
            return
        
        if os.path.splitext(dir_path)[1]:
            os.makedirs(os.path.dirname(dir_path), exist_ok=True)
        else:
            os.makedirs(dir_path, exist_ok=True)

        logger.info(f"Successfiully created local path: `{dir_path}`")


    def run_container(self, attempt: int=None):
        """Run a Docker container from the given image name."""
        if attempt:
            self.container_name += f"_attempt{attempt}"
        try:
            subprocess.run(
                ["docker", "run", "-d", "--name", self.container_name, self.image_name_with_tag],
                check=True
            )
            logger.info(f"Container {self.container_name} started successfully.")
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error starting container {self.container_name}: {e}\nAttempting again...")
            return False
        return True
    

    def copy_folder_from_container(self):
        """
        Copy a folder from the Docker container to the local host.
        
        Args:
            container_path (str): Path inside the Docker container to copy.
            local_path (str): Path on the local host to copy the folder to.
        """
        try:
            subprocess.run(
                ["docker", "cp", f"{self.container_name}:{self.container_path}/.", self.local_path],
                check=True
            )
            subprocess.run(
                ["docker", "cp", f"{self.container_name}:{self.container_path}/.git", self.local_path],
                check=False
            )
            logger.info(f"Folder {self.container_path} successfully copied to {self.local_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error copying folder from container {self.container_name}: {e}")
            return False
        return True
    
    def stop_and_remove_container(self):
        """Stop and remove the Docker container"""
        try:
            subprocess.run(["docker", "stop", self.container_name], check=True)
            subprocess.run(["docker", "rm", self.container_name], check=True)
            logger.info(f"Container {self.container_name} stopped and removed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error stopping/removing container {self.container_name}: {e}")
            return False
        return True

    def all_in_one_run_copy_remove_container(self):
        attempt = 0
        while True:
            attempt += 1

            if self.run_container(attempt):
                copy_success = False
                copy_dir = self.local_path + self.container_path.split("/")[-1]

                while True: 
                    if os.path.exists(copy_dir):
                        copy_success = True
                        break

                    if self.copy_folder_from_container():
                        copy_success = True
                        break
                
                if copy_success:
                    break

        while True:
            if self.stop_and_remove_container():
                break

