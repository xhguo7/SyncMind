"""
Docker manager
"""

import os
import re
import time
import subprocess

from utils.logger import logger
from syncbench.evaluator.exetest import ExecutionTest


class SandBoxManager(ExecutionTest):
    """Initialize execution env"""
    def __init__(self, args, instance, agent_revised_code, corresponding_context_code):
        super().__init__(args, instance, agent_revised_code, corresponding_context_code)
        # Repo
        self.repo_id = instance.repo_id
        self.repo_name = instance.repo_name
        self.repo_path = f"{args.root_path}{args.code_path}test_repo/"
        # Dockerfile
        self.dockerfile_path = os.path.join(f"{args.root_path}{args.code_path}", 'Dockerfile')
        self.dockerfile_content = []
        # Docker image
        self.image_id = ''
        self.image_name = f"xuehang/{instance.repo_id}_{instance.repo_name.lower()}"
        self.image_tag = args.env_python_version
        self.image_name_with_tag = f"{self.image_name}:{self.image_tag}"
        self.image_workdir = "/workspace"
        self.image_venv_dir = f"{self.image_workdir}/test_venv"
        self.image_venv_bin_dir = f"{self.image_venv_dir}/bin"
        # Docker container
        self.container_name = f"{self.image_name.replace('/', '_')}_container__{instance.fm_name}__{str(time.ctime()).replace(':', '_').replace(' ', '_')}"
        self.container_workdir = f"{self.image_workdir}/test_repo"
        # Additional unit test command
        self.env_additional_unittest_command = args.env_additional_unittest_command
        
    
    def create_docker_image(self):
        """Create docker image"""
        logger.info(f"Creating docker image for repository `{self.repo_id}_{self.repo_name}` in {self.repo_path}...")
        command = ["docker", "build", "-t", f"{self.image_name}:{self.image_tag}", "-f", self.dockerfile_path, "."]
        logger.pinfo(f"Running image creation command: {command}")

        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
            for line in process.stdout:
                print(line, end='')
            for line in process.stderr:
                print(line, end='')
            
            process.wait()
            return_code = process.returncode

        if return_code == 0:
            logger.info(f"Successfully created docker image '{self.image_name}:{self.image_tag}'")
        else:
            logger.error(f"Error creating docker image: {return_code}")
            raise Exception("Docker image creation failed.")
    
    
    def get_docker_image_id(self):
        """Get docker image ID for the created docker image"""
        command = ["docker", "images", "-q", self.image_name]
        result = subprocess.run(command, capture_output=True, text=True)
        
        image_id = result.stdout.strip()
        if image_id:
            logger.info(f"Docker image ID for docker image '{self.image_name}': {image_id}")
            return image_id
        else:
            logger.error(f"Image '{self.image_name}' not found.")
            raise Exception("Docker image not found.")
    
    
    def extract_package_name(self, requirement_line):
        """Extract package name"""
        package_name = re.split(r'[=<>!]', requirement_line, 1)[0].strip()
        return package_name
        
    
    def install_dependency_in_image(self, args):
        """Install dependencies in docker image"""
        logger.info(f"Adding dependencies install commands to Dockerfile for docker image '{self.image_name}'...")
        # Create a base Dockerfile
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
            f". {self.image_venv_bin_dir}/activate && pip install .; "
            f"elif [ -f setup.py ]; then "
            f". {self.image_venv_bin_dir}/activate && pip install .; "
            f"else "
            f"echo 'No pyproject.toml or setup.py found, skipping dependency installation'; "
            f"fi"
        ])
        
        # Install dependencies based on args or requirements.txt
        try:
            # (1) If have args.env_requirements
            if args.env_requirements != []:  # Install dependencies from my_repo_dict[repo_idx]['requirements']
                for item in args.env_requirements:
                    if ("==" in item) or (">" in item) or ("<" in item) or(">=" in item) or ("<=" in item):
                        install_command = f"RUN {self.image_venv_bin_dir}/pip install '{item.replace(' ', '')}'"
                    else: 
                        install_command = f"RUN {self.image_venv_bin_dir}/pip install {item}"
                    self.dockerfile_content.append(install_command)

            # (2) If have args.env_install_command
            elif args.env_install_command != []:  # Install dependencies from my_repo_dict[repo_idx]['install_command']
                for install_command_item in args.env_install_command:
                    install_command = f"RUN {self.image_venv_bin_dir}/{install_command_item}"
                    self.dockerfile_content.append(install_command)

            with open(self.dockerfile_path, 'w') as dockerfile:
                dockerfile.write("\n".join(self.dockerfile_content))
        
        finally:
            logger.info(f"Successfully created Dockerfile at {self.dockerfile_path}")
    

    def remove_docker_image(self):
        """Remove docker image after use"""
        self.get_docker_image_id()
        logger.info(f"Removing Docker image '{self.image_name}' with id '{self.image_id}'...")
        command = ["docker", "rmi", "-f", self.image_id]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.returncode == 0:
            logger.pinfo(f"Successfully removed docker image '{self.image_name}'")
        else:
            logger.error(f"Error removing docker image: {result.stderr}")
            raise Exception("Docker image removal failed.")
    
    
    def save_docker_image(self):
        """Save docker image to Docker Hub"""
        logger.info(f"Saving docker image '{self.image_name}' to Docker Hub...")

        # Tag the image for Docker Hub
        tagged_image = f"{self.args.dockerhub_username}/{self.image_name}:{self.image_tag}"
        subprocess.run(["docker", "tag", self.image_name, tagged_image], check=True)

        # Push the image to Docker Hub
        result = subprocess.run(["docker", "push", tagged_image], capture_output=True, text=True)
    
        if result.returncode == 0:
            logger.pinfo(f"Successfully saved Docker image '{tagged_image}' to Docker Hub.")
        else:
            logger.error(f"Error saving Docker image: {result.stderr}")
            raise Exception("Docker image save failed.")
        
    
    def check_docker_image(self, image_name, args):
        """
        Check if a Docker image with the specified name exists
        - If exists, return the image ID
        - If doesn't exist, create the image and return the new image ID.
        """
        logger.info(f"Checking if Docker image '{image_name}' exists...")

        # Check if the image exists
        command = ["docker", "images", "-q", image_name]
        result = subprocess.run(command, capture_output=True, text=True)
        
        image_id = result.stdout.strip()
        if image_id:
            logger.pinfo(f"Docker image '{image_name}' already exists with ID: {image_id}")
        else:
            logger.pinfo(f"Docker image '{image_name}' does not exist. Checking Dockerfile...")
            self.create_dockerfile(args)
            self.create_docker_image()
            image_id = self.get_docker_image_id()
            logger.pinfo(f"New Docker image '{image_name}' created with ID: {image_id}")
        
        return image_id
    
    
    def create_dockerfile(self, args):
        """Creates a Dockerfile if it does not already exist"""
        if not os.path.exists(self.dockerfile_path):
            logger.info(f"Dockerfile doesn't exist. Creating Dockerfile for current repo `{self.repo_id}_{self.repo_name}` in {self.repo_path}...")
            self.install_dependency_in_image(args)
        else:
            logger.info(f"Dockerfile already exists at {self.dockerfile_path}")
    