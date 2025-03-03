"""
Download the folder from a docker image to local host
"""

import os
import time
import subprocess
import pandas as pd
from openhands.core.logger import openhands_logger as logger


class DockerHandler:
    def __init__(self, instance: pd.Series, local_file_path: str, container_path: str):
        self.instance = instance
        self.image_name_with_tag = self.get_image_name()
        self.container_name = instance.instance_id + "__xuehang_docker__" + str(time.asctime()).replace(" ", "__").replace(":", "_") + f"__{container_path.split('/')[-1]}"
        self.container_path = container_path
        self.local_path = local_file_path.split("test_repo")[0]

    def get_image_name(self):
        instance_id = self.instance.instance_id
        image_name = instance_id.split("__")[0]
        image_tag = f"xuehang/{image_name}:3.11"
        return image_tag
    
    def run_container(self):
        """Run docker container"""
        try:
            subprocess.run(
                ["docker", "run", "-d", "--name", self.container_name, self.image_name_with_tag],
                check=True
            )
            logger.info(f"Container {self.container_name} started successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error starting container {self.container_name}: {e}")
            return False
        return True

    def copy_folder_from_container(self):
        """
        Copy a folder from the docker container to the local host.
        
        Args:
            container_path (str): Path inside the Docker container to copy.
            local_path (str): Path on the local host to copy the folder to.
        """
        try:
            subprocess.run(
                ["docker", "cp", f"{self.container_name}:{self.container_path}", self.local_path],
                check=True
            )
            logger.info(f"Folder {self.container_path} successfully copied to {self.local_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error copying folder from container {self.container_name}: {e}")
            return False
        return True
    
    def stop_and_remove_container(self):
        """Stop and remove container"""
        try:
            subprocess.run(["docker", "stop", self.container_name], check=True)
            subprocess.run(["docker", "rm", self.container_name], check=True)
            logger.info(f"Container {self.container_name} stopped and removed successfully.")
        except subprocess.CalledProcessError as e:
            logger.error(f"Error stopping/removing container {self.container_name}: {e}")
            return False
        return True

    def all_in_one_run_copy_remove_container(self):
        while True:
            if self.run_container():
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
