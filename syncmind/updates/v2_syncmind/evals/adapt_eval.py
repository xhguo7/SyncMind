"""
Adapt eval: evaluate recovery solution
"""

import os
import subprocess
import shutil
import time
import re
import ast
import json
import git
import docker
from pandas import Series
from colorama import init, Fore, Back, Style
init(autoreset=True)

from openhands.core.logger import openhands_logger as logger
from evaluation.benchmarks.syncmind.builds.aligner import align_agent_context
from evaluation.benchmarks.syncmind.builds.instance import InstanceProcessor
from evaluation.benchmarks.syncmind.evals.evaluator import DockerManager
from evaluation.benchmarks.syncmind.builds.loader import DockerHandler


SUBRPOCESS_TIMEOUT = 600

class DockerEvaluator(DockerManager):
    """Docker evaluator"""

    def __init__(self, instance: Series, test_result: dict) -> None:
        super().__init__(instance)
        # Instance
        self.instance = instance
        self.test_result = test_result
        self.instance_processor = InstanceProcessor(instance)
        self.task = test_result['resync_method']
        self.gold_summary = ast.literal_eval(instance.gold_summary)
        # Code
        self.if_gold_unit_test = False
        self.fm_name = instance.fm_name
        self.fm_file_name = instance.pyfile_name
        self.usage_test_file_path = instance.unittest_path
        self.agent_code_path = None
        self.agent_revised_code = None
        self.new_complete_context = instance.new_complete_context
        # Docker image
        self.image_id = self.check_docker_image()
        # Docker container
        self.container_workdir = f"{self.image_workdir}/test_repo"
        self.container = None
        self.container_id = ''
        self.container_name = f"{self.image_name.replace('/', '_')}__xuehang_evaluator__{str(time.ctime()).replace(':', '_').replace(' ', '_')}"
        # Additional test command
        self.env_additional_unittest_command = None
        # Init
        self.repo_clone_method = "image"  # online | image
        self.repo_clone_option = "efficient_clone"  # force_clone | efficient_clone
        self.clone_repo()
        self.instance_inits()

    def remove_repo(self):
        """Remove temporary directory"""
        if os.path.exists(self.repo_dir):
            subprocess.run(['rm', '-rf', self.repo_dir])
            logger.info(f"Successfully removed directory: {self.repo_dir}")
        else:
            logger.info(f"Directory does not exist: {self.repo_dir}")

    
    def clone_repo(self):
        """
        self.repo_clone_option:
        - "force_clone": clone must be completed; if cloned repo already exists, will remove cloned repo and reclone a new repo
        - "efficient_clone": if cloned repo already exists, will skip clone and used the cloned one

        self.repo_clone_method:
        - "online": clone repo from online GitHub repo
        - "image": clone repo from docker image
        """
        if not os.path.exists(self.repo_dir):
            # Clone from online GitHub repo
            if self.repo_clone_method == "online":
                try:
                    subprocess.run(["git", "clone", self.repo_url, self.repo_dir], check=True)
                    logger.info(f"Repository cloned to `{self.repo_dir}`")
                except subprocess.CalledProcessError as e:
                    logger.info(f"Failed to clone repository: {e}")
            # Clone from docker image
            else:
                docker_handler = DockerHandler(self.instance, self.repo_dir, "/workspace/test_repo")
                docker_handler.all_in_one_run_copy_remove_container()
        
        # Remove original repo and reclone
        else:
            if self.repo_clone_option == "force_clone":
                logger.info(f"Repository already exists at `{self.repo_dir}`. Removing the existing repo...")
                self.remove_repo()

                # Clone from online GitHub repo
                if self.repo_clone_method == "online":
                    try:
                        subprocess.run(["git", "clone", self.repo_url, self.repo_dir], check=True)
                        logger.info(f"Repository cloned to `{self.repo_dir}`")
                    except subprocess.CalledProcessError as e:
                        logger.info(f"Failed to clone repository: {e}")
                # Clone from docker image
                else:
                    docker_handler = DockerHandler(self.instance, self.repo_dir, "/workspace/test_repo")
                    docker_handler.all_in_one_run_copy_remove_container()
            else:
                logger.info(f"Repository already exists at `{self.repo_dir}`. Skipping repo clone...")


    def instance_inits(self):
        """Instance init"""
        self.agent_code_path, _, _ = self.instance_processor.instance_restoration()
        self.extract_agent_revised_code()
        self.agent_revised_code_with_context()
        self.init_instance_info()
    
    def init_instance_info(self):
        """@Override: init instance info"""
        with open(self.repo_source_path, 'r') as file:
            self.repo_source_data = json.load(file)
        repo_idx = int(self.repo_id) - 1
        self.test_method = self.repo_source_data[repo_idx]['test_method']
        self.env_requirements = self.repo_source_data[repo_idx]['requirements']
        self.env_install_command = self.repo_source_data[repo_idx]['install_command']
        self.env_additional_unittest_command = self.repo_source_data[repo_idx]['additional_unittest_command']
        
    def extract_agent_revised_code(self):
        """Agent solution"""
        self.agent_revised_code = self.test_result['updated_fm']
        if self.agent_revised_code == None:
            self.agent_revised_code = ""
        
    def agent_revised_code_with_context(self):
        """Get agent revised code"""
        self.agent_revised_code = align_agent_context(self.agent_revised_code, self.new_complete_context)
        with open(self.agent_code_path, 'w') as file:
            file.write(self.agent_revised_code)
        logger.info(f"Successfully saved aligned_code to '{self.agent_code_path}'")
        
    def remove_docker_container(self):
        """Stop and reomve docker container"""
        try:
            print(f"Stopping and removing container '{self.container_name}'...")
            self.run_command_in_container(["docker", "stop", self.container_name])
            self.run_command_in_container(["docker", "rm", self.container_name])
            print(f"Successfully removed container '{self.container_name}'")

        except Exception as e:
            print(f"Error occurred: {e}")
            raise
    
    def clean_directory_removal(self):
        """@Override the clean_directory_removal method to also remove the temporary repo folder on the host"""
        super().clean_directory_removal(self.repo_path)
        print(f"Removing temporary directory used for repository at '{self.repo_path}'")
        shutil.rmtree(self.repo_path, ignore_errors=True)
    
    def run_command_in_container(self, command):
        """Run in container"""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=SUBRPOCESS_TIMEOUT)
            return result
        except subprocess.CalledProcessError as e:
            return e
        
    def run_unittest_in_container(self, command):
        """Run execution test"""
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=SUBRPOCESS_TIMEOUT)
            print(Fore.GREEN + f"Execution succeeded!\nContainer output: \n{result.stdout}")
            return result
        except subprocess.TimeoutExpired as e:
            print(Fore.RED + f"[Timeout] Execution failed with timeout error: {e}")
            print(Fore.RED + f"[Timeout] Error output:\n{e.stderr}")
            print(Fore.RED + f"[Timeout] Standard output:\n{e.stdout}")
            if self.task in ['independent', "collaborative"]:
                if (e.stderr != None) or (e.stdout != None):
                    return {'error_num': 1, 'error': e}
                else:
                    return e
            else:  # args.task == dataset_construction
                return e
        except subprocess.CalledProcessError as e:
            print(Fore.RED + f"[Error] Execution failed with error: {e}")
            print(Fore.RED + f"[Error] Error output:\n{e.stderr}")
            print(Fore.RED + f"[Error] Standard output:\n{e.stdout}")
            if self.task in ['independent', "collaborative"]:
                if (e.stderr != None) or (e.stdout != None):
                    return {'error_num': 1, 'error': e}
                else:
                    return e
            else:  # args.task == dataset_construction
                return e
    
    def rectify_extraction(self, whole_str: str, keyword: str) -> int:
        """Parsing rectification"""
        print(Back.YELLOW + f"""{keyword.lstrip(' ')} count: {whole_str.split(keyword)[-2].split(' ')[-1]}""")
        try:
            ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
            whole_str = ansi_escape.sub('', whole_str)
            extracted_count = int(whole_str.split(keyword)[-2].split(' ')[-1])
            return extracted_count
        except ValueError as e:
            print(f"Discarding invalid `{keyword.lstrip(' ')}` count due to ValueError: {e}")
            return 0

    def pytest_result_count(self, exe_result):
        """Output parsing for unit test using pytest"""
        passed_count = xpassed_count = failed_count = xfailed_count = deselected_count = skipped_count = warning_count = error_count = 0
        collection_error_match = re.search(r"=+\s+ERRORS\s+=+\n(.|\n)*?=========================== short test summary info ============================", exe_result.stdout)
        if collection_error_match:
            error_count = 1

        passed_match = re.search(r" (\d+) passed", exe_result.stdout)
        xpassed_match = re.search(r" (\d+) xpassed", exe_result.stdout)
        failed_match = re.search(r" (\d+) failed", exe_result.stdout)
        xfailed_match = re.search(r" (\d+) xfailed", exe_result.stdout)
        deselected_match = re.search(r" (\d+) deselected", exe_result.stdout)
        skipped_match = re.search(r" (\d+) skipped", exe_result.stdout)
        warning_match = re.search(r" (\d+) warning", exe_result.stdout)
        warnings_match = re.search(r" (\d+) warnings", exe_result.stdout)
        error_match = re.search(r" (\d+) error", exe_result.stdout)
        errors_match = re.search(r" (\d+) errors", exe_result.stdout)

        if passed_match:
            passed_count = int(passed_match.group(1))
        if xpassed_match:
            xpassed_count = int(xpassed_match.group(1))
        if failed_match:
            failed_count = int(failed_match.group(1))
        if xfailed_match:
            xfailed_count = int(xfailed_match.group(1))
        if deselected_match:
            deselected_count = int(deselected_match.group(1))
        if skipped_match:
            skipped_count = int(skipped_match.group(1))
        if warning_match:
            warning_count = int(warning_match.group(1))
        elif warnings_match:
            warning_count = int(warnings_match.group(1))
        if error_match:
            error_count = int(error_match.group(1))
        elif errors_match:
            error_count = int(errors_match.group(1))

        if ((passed_count == 0) and (' passed' in exe_result.stdout)):
            passed_count = self.rectify_extraction(str(exe_result.stdout), " passed")
        if ((xpassed_count == 0) and (' xpassed' in exe_result.stdout)):
            xpassed_count = self.rectify_extraction(str(exe_result.stdout), " xpassed")
        if ((failed_count == 0) and (' failed' in exe_result.stdout)):
            failed_count = self.rectify_extraction(str(exe_result.stdout), " failed")
        if ((xfailed_count == 0) and (' xfailed' in exe_result.stdout)):
            xfailed_count = self.rectify_extraction(str(exe_result.stdout), " xfailed")
        if ((deselected_count == 0) and (' deselected' in exe_result.stdout)):
            deselected_count = self.rectify_extraction(str(exe_result.stdout), " deselected")
        if ((skipped_count == 0) and (' skipped' in exe_result.stdout)):
            skipped_count = self.rectify_extraction(str(exe_result.stdout), " skipped")
        if ((warning_count == 0) and (' warning' in exe_result.stdout)):
            warning_count = self.rectify_extraction(str(exe_result.stdout), " warning")
        elif ((warning_count == 0) and (' warnings' in exe_result.stdout)):
            warning_count = self.rectify_extraction(str(exe_result.stdout), " warnings")
        if ((error_count == 0) and (' error' in exe_result.stdout)):
            error_count = self.rectify_extraction(str(exe_result.stdout), " error")
        elif ((error_count == 0) and (' errors' in exe_result.stdout)):
            error_count = self.rectify_extraction(str(exe_result.stdout), " errors")

        total_count = passed_count + xfailed_count + failed_count + skipped_count + warning_count + error_count
        result_summary = {
            'total': total_count, 
            'passed': passed_count, 
            'xpassed': xpassed_count,
            'failed': failed_count, 
            'xfailed': xfailed_count,
            'deselected': deselected_count,
            'skipped': skipped_count,
            'warning': warning_count,
            'error': error_count
        }
        print(Back.CYAN + f"[Unit test summary]")
        print(Fore.CYAN + f"{result_summary}")
        return result_summary
    
    def unittest_result_count(self, exe_result):
        """Output parsing for unit test using unittest"""
        result = re.search(r"Ran (\d+) tests? in .* - (\d+) failures?, (\d+) errors?", exe_result.stdout)
        if result:
            total_count = int(result.group(1))
            failed_count = int(result.group(2))
            error_count = int(result.group(3))
            passed_count = total_count - failed_count - error_count
            warning_count = 0  # warning is not explicitly listed in unittest summary
            xfailed_count = 0  # xfailed is not explicitly listed in unittest summary
            xpassed_count = 0  # xfailed is not explicitly listed in unittest summary
            deselected_count = 0  # xfailed is not explicitly listed in unittest summary
            skipped_count = 0  # skipped is not explicitly listed in unittest summary
        else:
            total_count = failed_count = error_count = passed_count = deselected_count = skipped_count = warning_count = xfailed_count = xpassed_count = 0
            ran_match = re.search(r"Ran (\d+) tests?", exe_result.stdout)
            failure_match = re.search(r"(\d+) failures?", exe_result.stdout)
            error_match = re.search(r"(\d+) errors?", exe_result.stdout)
            if ran_match:
                total_count = int(ran_match.group(1))
            if failure_match:
                failed_count = int(failure_match.group(1))
            if error_match:
                error_count = int(error_match.group(1))
            passed_count = total_count - failed_count - error_count
        
        result_summary = {
            'total': total_count, 
            'passed': passed_count, 
            'xpassed': xpassed_count,
            'failed': failed_count, 
            'xfailed': xfailed_count,
            'deselected': deselected_count,
            'skipped': skipped_count,
            'warning': warning_count,
            'error': error_count
        }
        print(Back.CYAN + f"[Unit test summary]")
        print(Fore.CYAN + f"{result_summary}")
        return result_summary

    def test_result_count(self, exe_result):
        """Output parsing"""
        if self.test_method == 'pytest':
            result_summary = self.pytest_result_count(exe_result)
            test_count = result_summary['total']
        else:  # unittest
            result_summary = self.unittest_result_count(exe_result)
            test_count = result_summary['total']
        return test_count, result_summary
    
    def is_command_length_exceeded(self, command_list):
        """Check if current command_list exceeds docker's max command length limit"""
        arg_max = int(subprocess.run(['getconf', 'ARG_MAX'], capture_output=True, text=True).stdout.strip())
        command_str = ' '.join(command_list)
        if len(command_str) > arg_max:
            return True
        return False
    
    def recheck_env_installs(self):
        """Check env installs"""
        env_install_commands = ''
        if self.env_requirements != []:
            for item in self.env_requirements:
                if ("==" in item) or (">=" in item) or ("<=" in item):
                    install_command = f"{self.image_venv_bin_dir}/python -m pip install '{item.replace(' ', '')}'"
                else: 
                    install_command = f"{self.image_venv_bin_dir}/python -m pip install {item}"
                env_install_commands += (install_command + " && ")
        elif self.env_install_command != []:
            for install_command_item in self.env_install_command:
                install_command = f"{self.image_venv_bin_dir}/python -m {install_command_item}"
                env_install_commands += (install_command + " && ")
        return env_install_commands

    def run_unittest_for_history_code(self):
        """Run execution test"""
        restored_code_path = f"{self.container_workdir}/{self.agent_code_path.split('test_repo/')[1]}"
        test_file_path_in_container = f"{self.container_workdir}/{self.usage_test_file_path.split('test_repo/')[1]}"
        print(f"Running unit test using file `{test_file_path_in_container}` in Docker container `{self.container_name}`...")

        try:            
            run_command = [
                "docker", "run", "--rm", "--name", self.container_name,
                "-v", f"{self.agent_code_path}:{restored_code_path}",
                "-w", f"{self.container_workdir}",
                f"{self.image_name}:{self.image_tag}",
                "/bin/bash", "-c",
                f"export PYTHONPATH=$PYTHONPATH:{self.container_workdir} && "
                f"{self.image_venv_bin_dir}/python -m pip install -e . && "
                f"{self.image_venv_bin_dir}/python -m {self.test_method} -v {test_file_path_in_container} "
                f"{self.env_additional_unittest_command} "
            ]
            if self.is_command_length_exceeded(run_command):
                print("Current command length exceeds the system's maximum allowable length. Skipping this command...")
                return 'Invalid Test'
            exe_result = self.run_unittest_in_container(run_command)

            if not exe_result: 
                return 'Invalid Test'
                
            if isinstance(exe_result, dict):
                test_count = exe_result['error_num']
                error_content = f"{str(exe_result['error'])}\n{str(exe_result['error'].stderr)}\n{str(exe_result['error'].stdout)}"
                print(Fore.BLUE + f"Exucution test failed with the following error:\n{error_content}")  # error
                result_summary = {
                    'total': exe_result['error_num'], 
                    'passed': 0, 
                    'xpassed': 0,
                    'failed': 0, 
                    'xfailed': 0,
                    'deselected': 0,
                    'skipped': 0,
                    'warning': 0,
                    'error': exe_result['error_num']
                }
                execution_test_result = {'adapt_grade': 0, 'adapt_comment': str(error_content), 'exe_result': exe_result, 'summary': result_summary}
                return execution_test_result
            
            test_count, result_summary = self.test_result_count(exe_result)
            if test_count == 0:
                test_count = 1
                result_summary = {
                    'total': test_count, 
                    'passed': 0, 
                    'xpassed': 0,
                    'failed': 0, 
                    'xfailed': 0,
                    'deselected': 0,
                    'skipped': 0,
                    'warning': 0,
                    'error': test_count
                }
                execution_test_result = {'adapt_grade': 0, 'adapt_comment': str(exe_result.stderr), 'exe_result': exe_result, 'summary': result_summary}
                return execution_test_result
            
            if test_count:
                print(Fore.GREEN + f"Number of test evals in current unit test: {test_count}")

            if self.test_method == 'unittest':
                if exe_result.returncode == 0: 
                    execution_test_result = {'adapt_grade': 1, 'adapt_comment': exe_result.stderr, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    execution_test_result = {'adapt_grade': 0, 'adapt_comment': exe_result.stderr, 'exe_result': exe_result, 'summary': result_summary}
            elif self.test_method == 'pytest':
                adapt_comment = str(exe_result.stdout)
                pytest_start_str = "============================= test session starts =============================="
                if pytest_start_str in adapt_comment:
                    adapt_comment = pytest_start_str + adapt_comment.split(pytest_start_str)[1]
                if exe_result.returncode == 0:
                    if self.adapt_result_parsing_eval(result_summary):
                        execution_test_result = {'adapt_grade': 1, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
                    else:
                        execution_test_result = {'adapt_grade': 0, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    execution_test_result = {'adapt_grade': 0, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
            else:
                print(f"ERROR: Incorrect unit test method setting. Please correctly set unit test method and try again. ")
                raise
            
            return execution_test_result

        except subprocess.CalledProcessError as e:
            print(f"Error running execution test in Docker container: {e}")
            raise
    
    def adapt_result_parsing_eval(self, current_summary):
        """Adapt eval"""
        logger.info(f"Gold summary:    {self.gold_summary}")
        logger.info(f"Current summary: {self.gold_summary}")
        for key_item in self.gold_summary.keys():
            if int(current_summary[key_item]) != int(self.gold_summary[key_item]):
                return False
        return True

    def run_unittest(self):
        """Run unit test"""
        execution_test_result = self.run_unittest_for_history_code()
        return execution_test_result
        
    def sandbox_clean_up(self):
        self.remove_docker_container()
        # self.remove_docker_image()  # TODO: if need to remove image as well to save space
        self.clean_directory_removal()
