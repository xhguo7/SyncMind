"""
Init container
"""

import os
import shutil
import subprocess
import pandas as pd
from openhands.runtime.base import Runtime
from openhands.events.action import CmdRunAction
from openhands.core.logger import openhands_logger as logger
from evaluation.utils.shared import assert_and_raise
from evaluation.utils.shared import EvalMetadata
from evaluation.benchmarks.syncmind.builds.instance import InstanceProcessor

def get_docker_image_info(image_name):
    """Get docker image information"""
    try:
        command = f"docker images --format '{{{{.ID}}}} {{{{.Repository}}}}:{{{{.Tag}}}}' {image_name}"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode == 0 and result.stdout:
            output_lines = result.stdout.strip().split('\n')
            if len(output_lines) > 0:
                image_info = output_lines[0].split(' ')
                image_id = image_info[0]
                image_full_name = image_info[1]
                return image_id, image_full_name
            else:
                raise Exception(f"No images found for '{image_name}'.")

        else:
            raise Exception(f"Image '{image_name}' not found.")
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Error executing command: {e}")
        return None, None
    except Exception as ex:
        logger.error(f"An exception occurred: {ex}")
        return None, None


def get_container_names_by_image_id(image_id: str) -> list:
    """
    Takes the Docker image ID as input and returns a list of all container names associated with this image.
    
    Parameters:
        image_id (str): The ID of the Docker image.

    Returns:
        list: A list of container names associated with the provided image ID.
    """
    try:
        ps_command = f"docker ps -a --filter ancestor={image_id} --format '{{{{.Names}}}}'"
        result = subprocess.run(ps_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        container_names = result.stdout.decode('utf-8').strip().split('\n')
        return container_names if container_names != [''] else []
    
    except subprocess.CalledProcessError as e:
        error_message = e.stderr.decode('utf-8')
        logger.error(f"Error getting container names for image ID {image_id}: {error_message}")
        return []
    

def get_container_name_by_image(current_instance: str) -> str:
    """Gets the container name based on the image name."""
    known_image_name = "ghcr.io/all-hands-ai/runtime"
    image_id, image_name = get_docker_image_info(known_image_name)
    container_name_list = get_container_names_by_image_id(image_id)
    if len(container_name_list) > 0:
        return container_name_list[0]
    else: 
        return 'no_container_name_found'


def subprocess_run(command):
    """Run subprocess"""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result

def create_zip_archive(zip_dir):
    """Create zip"""
    try:
        zip_file_path = shutil.make_archive(zip_dir, 'zip', zip_dir)
        if os.path.exists(zip_file_path):
            logger.info(f"Zip file created successfully at: {zip_file_path}")
        else:
            logger.info(f"Error: Zip file was not created at: {zip_file_path}")

    except Exception as e:
        logger.error(f"An error occurred while creating the zip file: {e}")
        raise

def container_init_for_instance(
        runtime: Runtime, 
        instance: pd.Series, 
        metadata: EvalMetadata
    ) -> None:
    """Init docker container"""
    inst_processor = InstanceProcessor(instance)
    local_file_path, target_image_dir, target_image_path = inst_processor.instance_restoration()   
    local_repo_path = local_file_path.split("/test_repo")[0]
    local_zip_repo_path = local_repo_path + ".zip"
    runtime.config.workspace_mount_path = local_repo_path
    target_container_repo_path = "/workspace/"

    if not metadata.details["if_remote"]:
        new_command = "[ -d /workspace/test_repo ] && rm -rf /workspace/test_repo"
        action = CmdRunAction(command=new_command)
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(
            obs.exit_code == 0, 
            f'Failed: Failed to check and remove old-version test_repo if exists'
        )

        action = CmdRunAction(command="ls")
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(
            obs.exit_code == 0, 
            f'Failed: Failed to check workspace content'
        )
    
    create_zip_archive(local_repo_path.replace("/test_repo", ""))
    runtime.copy_to(local_zip_repo_path, target_container_repo_path)
    action = CmdRunAction(command="ls")
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0, 
        f'Failed: Failed to check workspace content'
    )

    try:
        os.remove(local_zip_repo_path)
        logger.info(f"Successfully removed zipped test_repo after copying: `{local_zip_repo_path}`")
    except Exception as e:
        logger.error(f"An unexpected error occurred when trying to remove the zipped test_repo after copying: `{local_zip_repo_path}`")
    