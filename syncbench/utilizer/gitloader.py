"""
Download git log for each function/method
"""

import os
import shutil
import subprocess
from utils.logger import logger


class GitLoader(object):
    def __init__(self, args, repo_id):
        # Repo
        self.repo_id = repo_id
        self.repo_name = args.repo_source_dict_list[int(repo_id)-1]['repo_name']
        self.repo_url = args.repo_source_dict_list[int(repo_id)-1]['github_link']
        self.repo_folder_name = f"{repo_id}_{self.repo_name}"
        self.repo_save_path = f"{args.root_path}{args.repo_path}"
        self.repo_dir = f"{self.repo_save_path}{self.repo_folder_name}/"
        # Docker
        self.image_tag = args.env_python_version
        
    
    # Download git log
    def get_repo_git_log(self):
        logger.info(f"\nDownloading git log for {self.repo_id} - {self.repo_name}")
        os.chdir(self.repo_dir)

        try:
            # Get the git log with error handling for encoding issues
            log = subprocess.run(["git", "log"], capture_output=True, text=True, errors='replace').stdout
            with open(f"{self.repo_save_path}{self.repo_id}_{self.repo_name}_git_log.txt", "w", encoding='utf-8', errors='replace') as file:
                file.write(log)
            logger.pinfo(f"'{self.repo_id}_{self.repo_name}' git log download success!\n")
        
        except Exception as e:
            logger.pinfo(f"An error occurred while fetching the git log: {e}")
        
        finally:
            os.chdir("..")

            # TODO: If needed, delete the repo directory
            # subprocess.run(["rm", "-rf", self.repo_dir])
    
    def get_repo_git_log_from_docker(self):
        """
        Load git log from an existing Docker container where the repository is located at /workspace/test_repo
        """
        logger.info(f"\nLoading git log from Docker image for {self.repo_id} - {self.repo_name}")
        
        container_name = f"git_log_extractor_{self.repo_id}_{self.repo_name}"
        image_name = f"xuehang/{self.repo_id}_{self.repo_name}:{self.image_tag}"
        
        try:
            # Start a new container from the image
            subprocess.run([
                "docker", "run",
                "-d",  # Run in detached mode
                "--name", container_name,
                image_name,
                "tail", "-f", "/dev/null"  # Keep container running
            ], check=True)
            
            # Execute git log command inside the container
            log = subprocess.run([
                "docker", "exec",
                container_name,
                "git", "-C", "/workspace/test_repo", "log"
            ], capture_output=True, text=True, errors='replace').stdout
            
            # Save the git log
            with open(f"{self.repo_save_path}{self.repo_id}_{self.repo_name}_git_log.txt", "w", encoding='utf-8', errors='replace') as file:
                file.write(log)
            
            logger.pinfo(f"'{self.repo_id}_{self.repo_name}' git log extraction from Docker success!\n")
        
        except subprocess.CalledProcessError as e:
            logger.pinfo(f"Docker operation failed: {e}")
        except Exception as e:
            logger.pinfo(f"An error occurred while fetching the git log from Docker: {e}")
        
        finally:
            # Clean up: Stop and remove the container
            try:
                subprocess.run(["docker", "stop", container_name], check=False)
                subprocess.run(["docker", "rm", container_name], check=False)
            except Exception as e:
                logger.pinfo(f"Error cleaning up Docker container: {e}")


class GitDownloader(object):
    def __init__(self, args):
        self.repo_source_dict_list = args.repo_source_dict_list
        self.git_log_path = f"{args.root_path}/{args.log_path.replace('/', '')}/{args.git_log_path.replace('/', '')}/"
    
    def get_repo_git_log(self, repo_id, repo_name, repo_github_link):
        """Get git logs"""
        repo_path = f'{self.git_log_path}{repo_name}'
        log_save_path = f"{self.git_log_path}{repo_id}_{repo_name}_git_log.txt"
        logger.info(f"\nProgress Update: {repo_id} - {repo_name}")

        if os.path.exists(repo_path):
            logger.pinfo(f"Removing existing repository directory: {repo_path}")
            shutil.rmtree(repo_path)

        subprocess.run(["git", "clone", repo_github_link, repo_path], check=True)
        os.chdir(repo_path)

        log_process = subprocess.run(["git", "log"], check=True, capture_output=True, text=True, errors='ignore')
        log = log_process.stdout
        with open(log_save_path, "w", encoding='utf-8') as file:
            file.write(log)

        os.chdir("..")
        subprocess.run(["rm", "-rf", f'{self.git_log_path}{repo_name}'])

    
    def git_download(self, args):
        """Download git logs"""
        if os.path.exists(self.git_log_path) and os.listdir(self.git_log_path):
            logger.info(f"Cleaning up git log directory: {self.git_log_path}")
            
            for item in os.listdir(self.git_log_path):
                item_path = os.path.join(self.git_log_path, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)

        
        for repo_idx in range(args.git_start, args.git_end):
            repo_id, repo_name, repo_github_link = self.repo_source_dict_list[repo_idx]['repo_id'], self.repo_source_dict_list[repo_idx]['repo_name'], self.repo_source_dict_list[repo_idx]['github_link']
            self.get_repo_git_log(repo_id, repo_name, repo_github_link)
        logger.info('\nGit Downloading Success!')
