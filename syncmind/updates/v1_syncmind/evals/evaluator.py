"""
Build docker image for current instance
"""

import os
import subprocess
import re
import json
import time
import shutil
import pandas as pd
from openhands.core.logger import openhands_logger as logger

class DockerManager:
    """Initialize DockerManager with current instance"""
    def __init__(self, instance: pd.Series):
        # Instance
        self.instance_id = instance.instance_id
        self.repo_id = self.instance_id.split('__')[0].split('_')[0]
        self.repo_name = self.instance_id.split('__')[0].split('_')[1]
        self.repo_url = instance.repo_url
        # Paths
        self.repo_dir = None
        self.local_tmp_dir = f'tmps/{self.instance_id}'
        self.local_code_dir_path = None
        # Instance env
        self.repo_source_path = None
        self.repo_source_data = None
        self.env_requirements = None
        self.env_install_command = None
        # Dockerfile
        self.dockerfile_path = None
        self.dockerfile_content = []
        # Docker image
        self.image_id = ''
        self.image_name = f"xuehang/{self.instance_id.split('__')[0]}"
        self.image_tag = "3.11"
        self.image_workdir = "/workspace"
        self.image_venv_dir = f"{self.image_workdir}/test_venv"
        self.image_venv_bin_dir = f"{self.image_venv_dir}/bin"
        self.dockerhub_username = 'xuehang'
        # Docker container
        self.container_name = f"{self.image_name.replace('/', '_')}_container_{str(time.ctime()).replace(':', '_').replace(' ', '_')}"
        self.container_workdir = f"{self.image_workdir}/test_repo"
        # Inits
        self.init_path_for_dockerfile()
        self.init_instance_info()
    
    def init_path_for_dockerfile(self):
        """Init repo_path and Dockerfile path args"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        dir_name = os.path.dirname(os.path.abspath(__file__)).split('/')[-1]
        self.local_code_dir_path = current_dir.replace(dir_name, self.local_tmp_dir)
        self.tmp_dir_creation(self.local_code_dir_path)  # create dir if doesn't exist
        self.repo_dir = os.path.join(self.local_code_dir_path, 'test_repo')
        self.dockerfile_path = os.path.join(self.local_code_dir_path, 'Dockerfile')
        self.repo_source_path = os.path.join(current_dir.replace(dir_name, 'data'), 'my_repo_dict.json')

    def init_instance_info(self):
        """Init instance info"""
        with open(self.repo_source_path, 'r') as file:
            self.repo_source_data = json.load(file)
        instance_idx = int(self.repo_id) - 1
        self.env_requirements = self.repo_source_data[instance_idx]['requirements']
        self.env_install_command = self.repo_source_data[instance_idx]['install_command']
    
    def tmp_dir_creation(self, tmp_dir):
        """Create temporary directory"""
        if not os.path.exists(tmp_dir):
            os.makedirs(tmp_dir)
            logger.info(f"Created temporary local directory: {tmp_dir}")
        else:
            logger.info(f"Directory already exists: {tmp_dir}")
    
    def create_docker_image(self):
        """Create docker image for current instance"""
        logger.info(f"Image '{self.image_name}:{self.image_tag}' not found. Creating a new image...")
        logger.info(f"Creating docker image for repository `{self.repo_id}_{self.repo_name}` in {self.repo_dir}...")
        command = ["docker", "build", "-t", f"{self.image_name}:{self.image_tag}", "-f", self.dockerfile_path, "."]
        logger.info(f"Running image creation command: {command}")
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            for line in process.stdout:
                logger.info(line.rstrip('\n'))
            for line in process.stderr:
                logger.info(line.rstrip('\n'))
            
            process.wait()
            return_code = process.returncode

        if return_code == 0:
            logger.info(f"Successfully created docker image '{self.image_name}:{self.image_tag}'")
        else:
            logger.info(f"Error creating docker image: {return_code}")
            raise Exception("Docker image creation failed.")
    
    def get_docker_image_id(self):
        """Get docker image ID for the created docker image"""
        command = ["docker", "images", "-q", f"{self.image_name}:{self.image_tag}"]
        result = subprocess.run(command, capture_output=True, text=True)
        
        image_id = result.stdout.strip()
        if image_id:
            logger.info(f"Docker image ID for docker image '{self.image_name}': {image_id}")
            return image_id
        else:
            logger.info(f"Image '{self.image_name}:{self.image_tag}' not found.")
            raise Exception("Docker image not found.")
    
    def extract_package_name(self, requirement_line):
        """Extract package name from a requirement line"""
        package_name = re.split(r'[=<>!]', requirement_line, 1)[0].strip()
        return package_name
        
    def install_dependency_in_image(self):
        """Install dependencies in docker image"""
        logger.info(f"Adding dependencies install commands to Dockerfile for docker image '{self.image_name}'...")
        self.dockerfile_content = [
            f"FROM python:{self.image_tag}",
            f"WORKDIR {self.image_workdir}", 
            f"RUN python -m venv {self.image_venv_dir}",
            f"RUN apt-get update && apt-get install -y git curl",
            f"RUN apt-get update && apt-get install -y ninja-build",
            f"RUN {self.image_venv_bin_dir}/pip install --upgrade pip",
            f"RUN git clone {self.repo_url} {self.image_workdir}/test_repo",
            f"WORKDIR {self.image_workdir}/test_repo",
            f"RUN {self.image_venv_bin_dir}/pip install poetry",
            f"RUN {self.image_venv_bin_dir}/pip install flit",
            f"RUN {self.image_venv_bin_dir}/pip install --upgrade setuptools",
            f"RUN {self.image_venv_bin_dir}/pip install -U pytest-asyncio"
        ]

        self.dockerfile_content.extend([
            f"RUN if [ -f pyproject.toml ]; then "
            f". {self.image_venv_bin_dir}/activate && "
            f"curl -sSL https://install.python-poetry.org | python3 - && "
            f"export PATH=$PATH:/root/.local/bin && "
            f"grep -q '[tool.poetry]' pyproject.toml && /root/.local/bin/poetry install || "
            f"pip install .; "
            f"elif [ -f setup.py ]; then "
            f". {self.image_venv_bin_dir}/activate && pip install .; "
            f"else "
            f"echo 'No pyproject.toml or setup.py found, skipping dependency installation'; "
            f"fi"
        ])
        
        try:
            if self.env_requirements != []:
                for item in self.env_requirements:
                    if ("==" in item) or (">=" in item) or ("<=" in item):
                        install_command = f"RUN {self.image_venv_bin_dir}/pip install '{item.replace(' ', '')}'"
                    else: 
                        install_command = f"RUN {self.image_venv_bin_dir}/pip install {item}"
                    self.dockerfile_content.append(install_command)

            elif self.env_install_command != []:
                for install_command_item in self.env_install_command:
                    install_command = f"RUN {self.image_venv_bin_dir}/{install_command_item}"
                    self.dockerfile_content.append(install_command)

            # Write the Dockerfile
            with open(self.dockerfile_path, 'w') as dockerfile:
                dockerfile.write("\n".join(self.dockerfile_content))
        
        finally:
            logger.info(f"Successfully created Dockerfile at {self.dockerfile_path}")

    def remove_tmp_dirs(self):
        """Remove tmp directories after use"""
        if os.path.exists(self.local_code_dir_path):
            shutil.rmtree(self.local_code_dir_path)
            print(f"Successfully removed directory and its contents at `{self.local_code_dir_path}`.")
        else:
            print(f"Directory {self.local_code_dir_path} does not exist.")
    
    def remove_docker_image(self):
        """Remove docker image after use"""
        self.get_docker_image_id()
        logger.info(f"Removing Docker image '{self.image_name}' with id '{self.image_id}'...")
        command = ["docker", "rmi", "-f", self.image_id]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.returncode == 0:
            logger.info(f"Successfully removed docker image '{self.image_name}'")
        else:
            logger.info(f"Error removing docker image: {result.stderr}")
            raise Exception("Docker image removal failed.")
    
    def save_docker_image(self):
        """Save docker image to Docker Hub"""
        logger.info(f"Saving docker image '{self.image_name}' to Docker Hub...")
        tagged_image = f"{self.image_name}:{self.image_tag}"
        subprocess.run(["docker", "tag", f"{self.image_name}:{self.image_tag}", tagged_image], check=True)
        result = subprocess.run(["docker", "push", tagged_image], capture_output=True, text=True)
    
        if result.returncode == 0:
            logger.info(f"Successfully saved Docker image '{tagged_image}' to Docker Hub.")
        else:
            logger.info(f"Error saving Docker image: {result.stderr}")
            raise Exception("Docker image save failed.")
        
    def create_dockerfile(self):
        """Creates a Dockerfile if it does not already exist"""
        if not os.path.exists(self.dockerfile_path):
            logger.info(f"Dockerfile doesn't exist. Creating Dockerfile for current repo `{self.repo_id}_{self.repo_name}` in {self.repo_dir}...")
            self.install_dependency_in_image()
        else:
            logger.info(f"Dockerfile already exists at {self.dockerfile_path}")
        

    def check_docker_image_and_create_if_not(self):
        """
        Check if a Docker image with the specified name exists
        - If exists, return the image ID
        - If doesn't exist, create the image and return the new image ID.
        """
        logger.info(f"Checking if Docker image '{self.image_name}:{self.image_tag}' exists...")
        command = ["docker", "images", "-q", f"{self.image_name}:{self.image_tag}"]
        result = subprocess.run(command, capture_output=True, text=True)
        
        image_id = result.stdout.strip()
        if image_id:
            logger.info(f"Docker image '{self.image_name}:{self.image_tag}' already exists with ID: {image_id}")
        else:
            logger.info(f"Docker image '{self.image_name}:{self.image_tag}' does not exist. Checking Dockerfile...")
            self.create_dockerfile()
            self.create_docker_image()
            image_id = self.get_docker_image_id()
            logger.info(f"New Docker image '{self.image_name}:{self.image_tag}' created with ID: {image_id}")
        
        self.image_id = image_id
        return image_id

    def check_docker_image(self):
        """
        Check if a Docker image with the specified name exists
        - If exists, return the image ID
        - If doesn't exist, create the image and return the new image ID.
        """
        logger.info(f"Checking if Docker image '{self.image_name}:{self.image_tag}' exists...")
        command = ["docker", "images", "-q", f"{self.image_name}:{self.image_tag}"]
        result = subprocess.run(command, capture_output=True, text=True)
        
        image_id = result.stdout.strip()
        if image_id:
            logger.info(f"Docker image '{self.image_name}:{self.image_tag}' already exists with ID: {image_id}")
        else:
            logger.info(f"Docker image '{self.image_name}:{self.image_tag}' does not exist. Pulling docker image from hub...")
            self.pull_image_from_hub()
            image_id = self.get_docker_image_id()
            logger.info(f"New Docker image '{self.image_name}:{self.image_tag}' created with ID: {image_id}")
        
        self.image_id = image_id
        return image_id

    def pull_image_from_hub(self):
        """Pull image from docker hub"""
        hub_image_name = f"{self.image_name}:{self.image_tag}"
        test_image_name = f"{self.image_name}:{self.image_tag}"
        try:
            logger.info(f"Pulling image `{hub_image_name}` from Docker Hub to local device...")
            subprocess.run(["docker", "pull", hub_image_name], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"An error occurred while pulling docker image `{hub_image_name}` from Docker Hub to local device: {e}")

