"""
SandBox execution test in isolated docker container
"""

import re
import os
import time
import shutil
import subprocess

from utils.logger import logger
from syncbench.utilizer.aligner import align_agent_context
from syncbench.evaluator.builder import SandBoxManager

class SandBoxET(SandBoxManager):
    def __init__(self, args, instance, agent_revised_code, corresponding_context_code, docker_image_id, if_gold_unit_test):
        super().__init__(args, instance, agent_revised_code, corresponding_context_code)
        # Task
        self.task = args.task
        self.timeout = args.timeout
        # Code
        self.if_gold_unit_test = if_gold_unit_test
        self.fm_file_name = instance.fm_file_name
        self.agent_code_path = instance.fm_file_path
        self.agent_revised_code = agent_revised_code
        self.context_code = corresponding_context_code
        # Repo
        self.clone_repository_from_image()
            
        self.agent_revised_code_with_context()
        # Docker image
        self.image_id = docker_image_id # override
        # Docker container
        self.container_workdir = f"{self.image_workdir}/test_repo"
        self.container = None
        self.container_id = ''
        self.container_name = f"{self.image_name.replace('/', '_')}_container__{instance.fm_name}__{str(time.ctime()).replace(':', '_').replace(' ', '_')}"
        # Additional test command
        self.env_additional_unittest_command = args.env_additional_unittest_command

    def ensure_agent_code_path_exists(self):
        """Check if the path exists"""
        if not os.path.exists(self.agent_code_path):
            if self.agent_code_path.endswith('/'):
                os.makedirs(self.agent_code_path)
                logger.info(f"Directory created at: {self.agent_code_path}")
            else:
                os.makedirs(os.path.dirname(self.agent_code_path), exist_ok=True)  # Make sure the directory exists
                logger.info(f"File created at: {self.agent_code_path}")
        else:
            logger.info(f"Path already exists: {self.agent_code_path}")
    
    def agent_revised_code_with_context(self):
        """Get agent revised code"""
        for context_idx in range(len(self.context_code)):
            if self.fm_file_name == self.context_code[context_idx]['name']:
                self.agent_revised_code = align_agent_context(self.agent_revised_code, self.context_code[context_idx]['complete_code'])
                self.ensure_agent_code_path_exists()
                with open(self.agent_code_path, 'w') as file:
                    file.write(self.agent_revised_code)
                logger.info(f"Successfully saved aligned_code to '{self.agent_code_path}'")

    def remove_docker_container(self):
        """Stop and reomve docker container"""
        try:
            logger.info(f"Stopping and removing container '{self.container_name}'...")
            self.run_command_in_container(["docker", "stop", self.container_name])
            self.run_command_in_container(["docker", "rm", self.container_name])
            logger.pinfo(f"Successfully removed container '{self.container_name}'")

        except Exception as e:
            logger.error(f"Error occurred: {e}")
            raise

    
    def clean_directory_removal(self):
        """Override the clean_directory_removal method to also remove the temporary repo folder on the host"""
        super().clean_directory_removal(self.repo_path)
        logger.info(f"Removing temporary directory used for repository at '{self.repo_path}'")
        shutil.rmtree(self.repo_path, ignore_errors=True)
    
    def run_command_in_container(self, command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            return result
        except subprocess.CalledProcessError as e:
            return e
        
    def run_unittest_in_container(self, command):
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=self.timeout)
            logger.info(f"Execution succeeded!\nContainer output: \n{result.stdout}")
            return result
        except subprocess.CalledProcessError as e:
            logger.error(f"Execution failed with error: {e}")
            logger.error(f"Error output:\n{e.stderr}")
            logger.error(f"Standard output:\n{e.stdout}")  # Add this line to capture stdout as well
        
            # Return
            if self.task in ['passive', 'proactive', 'ceiling']:
                if (e.stderr != None) or (e.stdout != None):
                    return {'error_num': 1, 'error': e}
                else:
                    return e
            else:  # args.task == dataset_construction
                return e
        except subprocess.TimeoutExpired as e:
            logger.error(f"[Subprocess Timeout Error]\n{e}\n[Invalid Test due to Timeout] Current unit test has been running for more than {self.timeout}s. Will skip current instance and move on to the next one...")
            return 'Timeout'
    
    
    def rectify_extraction(self, whole_str: str, keyword: str) -> int:
        """Parsing rectification"""
        logger.info_with_yellow_background(f"""{keyword.lstrip(' ')} count: {whole_str.split(keyword)[-2].split(' ')[-1]}""")
        try:
            ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
            whole_str = ansi_escape.sub('', whole_str)
            extracted_count = int(whole_str.split(keyword)[-2].split(' ')[-1])
            return extracted_count
        except ValueError as e:
            logger.error(f"Discarding invalid `{keyword.lstrip(' ')}` count due to ValueError: {e}")
            return 0

    
    def pytest_result_count(self, exe_result):
        """Parsing-based execution evaluation using pytest"""
        passed_count = xpassed_count = failed_count = xfailed_count = deselected_count = skipped_count = warning_count = error_count = 0

        collection_error_match = re.search(r"=+\s+ERRORS\s+=+\n(.|\n)*?=========================== short test summary info ============================", exe_result.stdout)
        if collection_error_match:
            # If there's an error during collection, count it
            error_count = 1

        # Match the usual test result summary
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
        
        # Return the summary
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

        logger.info_with_cyan_background(f"[Unit test summary]")
        logger.print_colored_text(f"{result_summary}", logger.hex_color_dict['cyan'])
        
        return result_summary
    
    
    def unittest_result_count(self, exe_result):
        """Parsing-based execution evaluation using unittest"""
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
            # Handle the case where only some groups are present
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

        logger.info_with_cyan_background(f"[Unit test summary]")
        logger.print_colored_text(f"{result_summary}", logger.hex_color_dict['cyan'])

        return result_summary
    
    def test_result_count(self, exe_result):
        """Count the number of tests: passes, failed, skipped"""
        # Parse the number of tests run
        if self.test_method == 'pytest':
            result_summary = self.pytest_result_count(exe_result)
            test_count = result_summary['total']
        else:  # unittest
            result_summary = self.unittest_result_count(exe_result)
            test_count = result_summary['total']
        return test_count, result_summary
    
    
    def is_command_length_exceeded(self, command_list):
        """Check if current command_list exceeds docker's max command length limit"""
        # Get the maximum command length allowed on the system
        arg_max = int(subprocess.run(['getconf', 'ARG_MAX'], capture_output=True, text=True).stdout.strip())

        # Join the command list into a single string
        command_str = ' '.join(command_list)

        # Check if the length of the command exceeds ARG_MAX
        if len(command_str) > arg_max:
            return True
        return False
    
    
    def run_unittest_for_gold_code(self):
        """Run unit test for gold code"""
        test_file_path_in_container = f"{self.container_workdir}/{self.usage_test_file_path.split('test_repo/')[1]}"
        test_module_path = self.usage_test_file_path.split('test_repo/')[1]
        logger.info(f"Running unit test using file `{test_file_path_in_container}` in Docker container `{self.container_name}`...")
        
        # Run unit test
        try:
            run_command = [
                "docker", "run", "--rm", "--name", self.container_name,
                "-w", f"{self.container_workdir}",
                f"{self.image_name}:{self.image_tag}",
                "/bin/bash", "-c",
                f"export PYTHONPATH=$PYTHONPATH:{self.container_workdir} && "
                f"{self.image_venv_bin_dir}/python -m pip install -e . && "
                f"{self.image_venv_bin_dir}/python -m {self.test_method} -v {test_file_path_in_container} "
                f"{self.env_additional_unittest_command} "
            ]
            if self.is_command_length_exceeded(run_command):
                logger.warning("Current command length exceeds the system's maximum allowable length. Skipping this command...")
                return 'Invalid Test'
            exe_result = self.run_unittest_in_container(run_command)

            # If timeout
            if exe_result == 'Timeout':
                return exe_result

            # If exe_result == None
            if not exe_result: 
                return 'Invalid Test'
            
            # Out-of-sync recovery adapt eval exclusive: if error before unit test
            if (self.task in ['passive', 'proactive', 'ceiling']) and (type(exe_result) == dict):
                test_count = exe_result['error_num']
                error_content = f"{str(exe_result['error'])}\n{str(exe_result['error'].stderr)}\n{str(exe_result['error'].stdout)}"
                logger.testing(f"Exucution test failed with the following error:\n{error_content}")
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
            
            # Count the number of tests: passes, failed, skipped
            test_count, result_summary = self.test_result_count(exe_result)
            if test_count:
                logger.info(f"Number of tests executed in gold unit test: {test_count}")  # passed + failed + error
            else:
                logger.info("No tests were executed in gold unit test.")
                return 'Invalid Test'
            
            # Save
            if self.test_method == 'unittest':
                if exe_result.returncode == 0: 
                    execution_test_result = {'adapt_grade': 1, 'adapt_comment': exe_result.stderr, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    execution_test_result = {'adapt_grade': 0, 'adapt_comment': exe_result.stderr, 'exe_result': exe_result, 'summary': result_summary}
            elif self.test_method == 'pytest':
                adapt_comment = str(exe_result.stdout)
                if exe_result.returncode == 0: 
                    execution_test_result = {'adapt_grade': 1, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    if test_count == 0:
                        execution_test_result = {'adapt_grade': 0, 'adapt_comment': str(exe_result.stderr), 'exe_result': exe_result, 'summary': result_summary}
                    else:
                        execution_test_result = {'adapt_grade': 0, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
            else:
                logger.error(f"ERROR: Incorrect unit test method setting. Please correctly set unit test method and try again. ")
                raise
            
            # Return
            return execution_test_result

        except subprocess.CalledProcessError as e:
            logger.error(f"Error running execution test in Docker container: {e}")
            raise

    
    def run_unittest_for_history_code(self):
        """Run unit test for history code"""
        restored_code_path = f"{self.container_workdir}/{self.agent_code_path.split('test_repo/')[1]}"
        test_file_path_in_container = f"{self.container_workdir}/{self.usage_test_file_path.split('test_repo/')[1]}"
        logger.info(f"Running unit test using file `{test_file_path_in_container}` in Docker container `{self.container_name}`...")

        try:            
            # Run unit test
            run_command = [
                "docker", "run", "--rm", "--name", self.container_name,
                "-v", f"{self.agent_code_path}:{restored_code_path}",  # Mount the file into the container
                "-w", f"{self.container_workdir}",
                f"{self.image_name}:{self.image_tag}",
                "/bin/bash", "-c",
                f"export PYTHONPATH=$PYTHONPATH:{self.container_workdir} && "
                f"{self.image_venv_bin_dir}/python -m pip install -e . && "
                f"{self.image_venv_bin_dir}/python -m {self.test_method} -v {test_file_path_in_container} "
                f"{self.env_additional_unittest_command} "
            ]
            if self.is_command_length_exceeded(run_command):
                logger.warning("Current command length exceeds the system's maximum allowable length. Skipping this command...")
                return 'Invalid Test'
            exe_result = self.run_unittest_in_container(run_command)

            # If timeout
            if exe_result == 'Timeout':
                return exe_result

            # If exe_result == None
            if not exe_result: 
                return 'Invalid Test'
                
            # Out-of-sync recovery adapt eval exclusive: if error before unit test
            if (self.task in ['passive', 'proactive', 'ceiling']) and (type(exe_result) == dict):
                test_count = exe_result['error_num']
                error_content = f"{str(exe_result['error'])}\n{str(exe_result['error'].stderr)}\n{str(exe_result['error'].stdout)}"
                logger.testing(f"Exucution test failed with the following error:\n{error_content}")  # error
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
            
            # Count the number of tests: passes, failed, skipped
            test_count, result_summary = self.test_result_count(exe_result)

            # If error before unit test
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
                logger.info(f"Number of test evals in current unit test: {test_count}")
            
            # Save
            if self.test_method == 'unittest':
                if exe_result.returncode == 0: 
                    adapt_comment = str(exe_result.stderr)
                    execution_test_result = {'adapt_grade': 1, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    execution_test_result = {'adapt_grade': 0, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
            elif self.test_method == 'pytest':
                adapt_comment = str(exe_result.stdout)
                if exe_result.returncode == 0: 
                    execution_test_result = {'adapt_grade': 1, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
                else: 
                    execution_test_result = {'adapt_grade': 0, 'adapt_comment': adapt_comment, 'exe_result': exe_result, 'summary': result_summary}
            else:
                logger.error(f"ERROR: Incorrect unit test method setting. Please correctly set unit test method and try again. ")
                raise
            
            # Return
            return execution_test_result

        except subprocess.CalledProcessError as e:
            logger.error(f"Error running execution test in Docker container: {e}")
            raise

    
    def run_unittest(self):
        """Run unit test"""
        if self.if_gold_unit_test:
            execution_test_result = self.run_unittest_for_gold_code()
        else:
            execution_test_result = self.run_unittest_for_history_code()
        return execution_test_result
        
    def sandbox_clean_up(self):
        self.remove_docker_container()
        # self.remove_docker_image()  # TODO: comment out if needed
        self.clean_directory_removal()
