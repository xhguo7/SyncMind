"""
Callee dataset
"""
import json
import git
import ast
import os
import sys
import time
import shutil
from datetime import datetime
from textwrap import dedent
import autopep8
import re
from typing import List, Dict

from syncbench.evaluator.exetest import ExecutionTest
from syncbench.evaluator.builder import SandBoxManager
from syncbench.evaluator.tester import SandBoxET
from syncbench.constructor.instancer import (
    InstanceConfig, 
    remove_fm_in_context_code, 
    generate_code_revision_log
)
from syncbench.utilizer.function_filter import FunctionFilter
from syncbench.utilizer.method_filter import MethodFilter
from syncbench.utilizer.gitloader import GitLoader
from syncbench.utilizer.tracer import CodeHistoryTracer
from utils.logger import ConstructLogger, logger
from utils.json_util import read_test_data

# Set recursion limit
sys.setrecursionlimit(10000)

class CustomEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

class Extractor(ast.NodeVisitor):
    def __init__(
            self, 
            args, 
            repo_url: str, 
            repo_id: str, 
            repo_name: str
        ) -> None:

        # Task
        self.args = args
        self.functions = []
        self.methods = []
        self.current_file_content = None
        self.current_file_name = None
        self.context_code = []

        # Repo
        self.repo_url = repo_url
        self.repo_id = repo_id
        self.repo_name = repo_name  # save the repository name
        self.repo_folder_name = f"{repo_id}_{args.repo_source_dict_list[int(repo_id)-1]['repo_name']}"
        self.clone_dir = f"{args.root_path}{args.repo_path}{self.repo_folder_name}/"
        self.clone_method = 'docker'  # docker | github
        self.curr_repo_image_name = f"xuehang/{self.repo_id}_{self.repo_name.lower()}"
        self.git_clone_repo()

    def relocate_absolute_path_for_exetest(self, original_path: str) -> str:
        """Path relocation"""
        return original_path.replace(f"{self.repo_id}_{self.repo_name}", "test_repo")
    
    
    def git_clone_repo(self):
        """Clone repo from GitHub"""
        if os.path.exists(self.clone_dir):
            logger.info(f"Repository already exists at '{self.clone_dir}'. Skipping clone.")
        else:
            os.makedirs(self.clone_dir, exist_ok=True)
            if self.clone_method == 'docker':
                logger.pinfo(f"Cloning repository from '{self.curr_repo_image_name}' to '{self.clone_dir}'...")
                repo_info = {
                    'repo_id': self.repo_id,
                    'repo_name': self.repo_name,
                    'repo_url': self.repo_url
                }
                repo_instance = InstanceConfig(**repo_info)
                sandbox_manager = SandBoxManager(self.args, repo_instance, None, None)
                self.curr_repo_image_id = sandbox_manager.check_docker_image(self.curr_repo_image_name, self.args)
                sandbox_manager.clone_repository_from_image(self.clone_dir, True)

            else:
                logger.pinfo(f"Cloning repository from '{self.repo_url}' to '{self.clone_dir}'...")
                git.Repo.clone_from(self.repo_url, self.clone_dir)
        
        logger.pinfo(f"Successfully cloned `{self.repo_id}_{self.repo_name}` to `{self.clone_dir}`")

    
    def correct_indentation(self, code: str) -> str:
        """Python format correction"""
        try:
            corrected_code = autopep8.fix_code(code, options={'indent_size': 4})
            return corrected_code
        except Exception as e:
            logger.warning(f"[Invalid Code Format Correction] An error occurred:\n{e}\nDirectly returning original code...")
            return code

    def remove_repo_directory(self):
        """Repo removal"""
        if os.path.exists(self.clone_dir):
            shutil.rmtree(self.clone_dir)
            logger.info(f"Successfully removed repository at '{self.clone_dir}'")
        else:
            logger.info(f"Repository at '{self.clone_dir}' does not exist. Skipping repo removal...")

    def clean_remove_dir(self, path_to_remove: str):
        """Clean removal"""
        for root, dirs, files in os.walk(path_to_remove, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove file `{file_path}`: {e}\nAttempting file removal again...")

            for name in dirs:
                dir_path = os.path.join(root, name)
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    logger.warning(f"Failed to remove directory `{dir_path}`: {e}\nAttempting directory removal again...")

        try:
            shutil.rmtree(path_to_remove, ignore_errors=True)
            logger.info(f"Successfully removed directory at '{path_to_remove}'")
        except Exception as e:
            logger.warning(f"Failed to remove directory `{path_to_remove}`: {e}\nAttempting directory removal again...")
            self.clean_remove_dir(path_to_remove)

    def visit_FunctionDef(self, node):
        try:
            # Capture the source code with correct indentation
            source_code = dedent(ast.get_source_segment(self.current_file_content, node))
            source_code = self.correct_indentation(source_code)

            # Determine if it's a method or function
            if isinstance(node.parent, ast.ClassDef):
                type_code = "method"
                self.methods.append({
                    "type": type_code, 
                    "name": node.name,
                    "file_name": os.path.basename(self.current_file_name),
                    "whole_file_path": self.current_file_name,
                    "repo_id": self.repo_id, 
                    "repo_name": self.repo_name,
                    "repo_url": self.repo_url,
                    "code": source_code,
                    "context": self.context_code
                })
            else:
                type_code = "function"
                self.functions.append({
                    "type": type_code,
                    "name": node.name,
                    "file_name": os.path.basename(self.current_file_name),
                    "whole_file_path": self.current_file_name, 
                    "repo_id": self.repo_id, 
                    "repo_name": self.repo_name,
                    "repo_url": self.repo_url,
                    "code": source_code,
                    "context": self.context_code
                })

            self.generic_visit(node)
        except RecursionError:
            logger.warning(f"RecursionError encountered while processing function {node.name}. Skipping this function.")
        except Exception as e:
            logger.warning(f"An error occurred while processing function {node.name}: {e} -> Skipping this function")

    def visit_ClassDef(self, node):
        try:
            self.generic_visit(node)
        except RecursionError:
            logger.warning(f"RecursionError encountered while processing class {node.name}. Skipping this class.")
        except Exception as e:
            logger.warning(f"An error occurred while processing class {node.name}: {e} -> Skipping this class")
    
    def collect_context_code(self, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                code = file.read()
        except UnicodeDecodeError:  # if is not 'utf-8' encoding
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                code = file.read()
            code = code.encode('utf-8', errors='ignore').decode('utf-8')  # transform code to 'utf-8' encoding
        
        code = self._simplify_imports(code)
        self.context_code = [{"name": os.path.basename(file_path), "whole_file_path": file_path, "code": code}]
        self._collect_imported_dependencies(code, file_path)
    
    
    def _simplify_imports(self, code):
        def replace_import(match):
            from_part = match.group(1).split('.')[-1]
            return f'from {from_part} import {match.group(2)}'
        
        return re.sub(r'from\s+([\w\.]+)\s+import\s+([\w_]+)', replace_import, code)

    
    def _collect_imported_dependencies(self, code: str, file_path: str):
        module_dir = os.path.dirname(file_path)
        import_statements = [line for line in code.splitlines() if line.startswith("from ") or line.startswith("import ")]
        for line in import_statements:
            parts = line.split()
            if parts[0] == "from" and parts[1] != ".":
                module_name = parts[1].split('.')[-1]
                dependency_file = os.path.join(self.clone_dir, module_name.replace('.', '/') + '.py')
                if os.path.exists(dependency_file) and not any(dep['name'] == os.path.basename(dependency_file) for dep in self.context_code):
                    with open(dependency_file, 'r', encoding='utf-8') as dep_file:
                        dep_code = dep_file.read()
                        dep_code = self._simplify_imports(dep_code)
                        self.context_code.append({"name": os.path.basename(dependency_file), "whole_file_path": dependency_file, "code": dep_code})



class CalleeConstructor(Extractor):
    def __init__(self, args, repo_id: str = None) -> None:
        # Repo
        self.repo_github_url = args.repo_source_dict_list[int(repo_id)-1]['github_link']
        self.repo_name = args.repo_source_dict_list[int(repo_id)-1]['repo_name']
        self.repo_id = repo_id
        # Docker
        self.dataset_version = args.dataset
        self.curr_repo_image_id = ''
        self.git_method = 'docker'  # github | docker
        # Path
        self.dataset_save_path = f"{args.root_path}{args.dataset_path}"
        self.code_path = f"{args.root_path}{args.code_path}"
        # Dataset construction
        self.max_extracted_data_to_be_filtered = args.max_extraction_data_length
        self.preprocess_filter_strictness = args.preprocess_filter_strictness
        self.filtered_fm_dict_list = []
        self.processed_fm_dict_list = []
        self.test_type = ''
        self.logger = ConstructLogger(f"{args.root_path}/{args.log_path.replace('/', '')}/{args.dataset_construction_log_path.replace('/', '')}/{self.repo_id}_{self.repo_name}_{args.dataset}_construct_log.json")  # initialize logger
        self.check_code_path_valid()
        super().__init__(args=args, repo_url=self.repo_github_url, repo_id=repo_id, repo_name=self.repo_name)
    
    def _async_wait(self, delay: int=120):
        logger.info(f"Let's wait for {delay} seconds to avoid repo async...")
        time.sleep(delay)

    def check_code_path_valid(self):
        """Check if code directory exists"""
        if os.path.exists(self.code_path):
            logger.info(f"Code directory exists at '{self.code_path}'. Will remove the existing one and recreate the code directory.")
            shutil.rmtree(self.code_path)
            logger.pinfo(f"Successfully removed the existing code directory at '{self.code_path}'")

        os.makedirs(self.code_path, exist_ok=True)
        logger.info(f"Successfully created code directory at '{self.code_path}'")

    def get_current_git_log(self, args):
        git_loader = GitLoader(args, self.repo_id)
        if self.git_method == 'docker':
            git_loader.get_repo_git_log_from_docker()
        else:
            git_loader.get_repo_git_log()

    def save_to_json(self, data, save_path):
        with open(save_path, 'w') as data_file:
            json.dump(data, data_file, indent=4)
        logger.info(f"Successfully saved data to '{save_path}")

    def list_reverse(self, original_list):
        """Reverse a list via slicing"""
        reversed_list = original_list[::-1]
        return reversed_list
    
    def filter_via_execution_test(
            self, 
            args, 
            new_instance: InstanceConfig, 
            tested_code: str, 
            context_code: str, 
            if_gold_unit_test: bool = False
        ):
        """Launch Execution Test"""
        new_instance.usage_test_file_path = self.relocate_absolute_path_for_exetest(new_instance.usage_test_file_path)
        new_instance.fm_file_path = self.relocate_absolute_path_for_exetest(new_instance.fm_file_path)

        if args.unittest_exetest_method == 1:
            self.curr_repo_image_id = args.env_image_id
            logger.info("Preparing docker env for execution test...")
            self.clean_remove_dir(self.code_path)
            sandbox_manager = SandBoxManager(args, new_instance, tested_code, context_code)
            if len(self.curr_repo_image_id) == 0:
                self.curr_repo_image_id = sandbox_manager.check_docker_image(self.curr_repo_image_name, args)
            sandbox_manager.clone_repository_from_image()
            sandbox_manager.save_code_to_file()

            logger.info(f"Using docker image with ID: {self.curr_repo_image_id}")
            exe_tester = SandBoxET(args, new_instance, tested_code, context_code, self.curr_repo_image_id, if_gold_unit_test)
            
            test_eval = exe_tester.run_unittest()
            exe_tester.sandbox_clean_up()
            
        else:  # args.unittest_exetest_method == 0
            exe_tester = ExecutionTest(args, new_instance, tested_code, context_code)
            test_eval = exe_tester.execution_test(args)
            exe_tester.remove_after_execution_test()

        return test_eval
    
    def get_context_code_item(
            self, 
            context_code_list: List, 
            context_file_name: str
        ):
        for context_item in context_code_list:
            if context_item['name'] == context_file_name:
                return context_item

    
    def unittest_filtering(
            self, 
            args, 
            original_exe_result: Dict, 
            gold_exe_result: Dict
        ) -> bool:
        """
        Unit test filtering
        - valid: return True
        - invalid: return False
        """
        if ('Ran 0 tests in' in original_exe_result['exe_result'].stderr) or ('Ran 0 tests in' in gold_exe_result['exe_result'].stderr):
            return False
        return True
    
    
    def fm_filtering(self, args, test_item):
        """Function & method code filtering"""
        new_filtered_fm_dict_list = []
        fm_list = test_item['fms']
        usage_test_file_path = test_item['usage_test_file']
        usage_test_root_path = test_item['usage_root_path']
        print_progress_count = 0

        if not usage_test_file_path.endswith('.py'):
            logger.info(f"[General filtering] Invalid unit test.")
            return new_filtered_fm_dict_list

        gold_exe_result_dict = {'fm_file_path': '', 'exe_result': None}

        for fm_dict in fm_list:
            print_progress_count += 1
            logger.print_colored_text(f"\n{'=' * 25}  Function/method filtering {print_progress_count}/{len(fm_list)}: [{test_item['usage_test_file'].split('/')[-1]}] -> [{fm_dict['file_name']}] -> [{fm_dict['name']}]  {'=' * 25}", logger.hex_color_dict['cyan'])
            
            new_instance_config = {
                'fm_type': fm_dict['type'],
                'fm_name': fm_dict['name'], 
                'fm_file_name': fm_dict['file_name'],
                'python_file_list': [fm_dict['file_name']],
                'gold_code': fm_dict['code'],
                'fm_context_dict': fm_dict['context'],
                'fm_file_path': fm_dict['whole_file_path'],
                'usage_test_file_path': test_item['usage_test_file'],
                'repo_id': fm_dict['repo_id'], 
                'repo_name': fm_dict['repo_name'], 
                'repo_url': fm_dict['repo_url'],
            }
            new_instance = InstanceConfig(**new_instance_config)

            new_data_check = {
                'usage_test_file_path': usage_test_file_path, 
                'fm_type': new_instance.fm_type,
                'fm_name': new_instance.fm_name,
                'fm_file_name': new_instance.fm_file_name,
                'fm_file_path': new_instance.fm_file_path
            }
            if new_data_check in self.processed_fm_dict_list:
                logger.pinfo(f"[General filtering] Skipping current {new_instance.fm_type} `{new_instance.fm_name}` due to duplicate processing.")
                continue
            else:
                self.processed_fm_dict_list += [new_data_check]

            try:
                tracer = CodeHistoryTracer(self.clone_dir)
            except Exception as e:
                logger.warning(f"An error occurred when tracing commit history: {e}\nAttemptaining again...")
                sandbox_manager = SandBoxManager(args, new_instance, None, None)
                self.curr_repo_image_id = sandbox_manager.check_docker_image(self.curr_repo_image_name, args)
                sandbox_manager.clone_repository_from_image(self.clone_dir, True)
                tracer = CodeHistoryTracer(self.clone_dir)
                logger.pinfo(f"Update: Commit tracing success!")

            fm_history = tracer.get_function_history(new_instance.fm_file_path, new_instance.fm_name)
            if (fm_history == None) or (len(fm_history)==0):  # if no function/method code history versions
                logger.info_with_pink_background(f"[Invalid test] {new_instance.fm_name} has no history versions.")
                continue

            if args.commit_trace_mode == 1:
                fm_history = [fm_history[-1]]
                
            # Commit history tracing
            for entry in fm_history: 
                commit_hash = entry['commit']
                new_instance.out_of_sync_code = entry['code']
                # [Skip current function/method] skip current commit: if no code change for function/method code
                if new_instance.gold_code == entry['code']:
                    logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) is invalid because the code of {new_instance.fm_type} `{new_instance.fm_name}` is unchanged.")
                    continue
                # [Skip current function/method] skip current function/method due to parsing error
                if entry['code'] == None:
                    logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) for `{new_instance.fm_name}` is invalid due to parsing error.")
                    continue

                try:
                    with open(new_instance.fm_file_path, "r") as file:
                        complete_curr_new_context_code = file.read()
                except Exception as e:
                    logger.warning(f"An error occurred when trying to restore the out-of-sync code: {e}\nAttempting again...")
                    sandbox_manager = SandBoxManager(args, new_instance, None, None)
                    self.curr_repo_image_id = sandbox_manager.check_docker_image(self.curr_repo_image_name, args)
                    sandbox_manager.clone_repository_from_image(self.code_path, force_remove=True)
                    
                    try:
                        with open(new_instance.fm_file_path, "r") as file:
                            complete_curr_new_context_code = file.read()
                    except Exception as e:
                        logger.warning(f"Error persists when trying to restore the out-of-sync code: {e}\nSkipping current commit...")
                        continue

                complete_curr_old_context_code = tracer.restore_file_code(new_instance.fm_file_path, commit_hash)
                curr_new_context_code = self.correct_indentation(remove_fm_in_context_code(complete_curr_new_context_code, new_instance.fm_name))  # filtered out fm_code
                curr_old_context_code = self.correct_indentation(remove_fm_in_context_code(complete_curr_old_context_code, new_instance.fm_name))  # filtered out fm_code
                new_context_code = [{'name': new_instance.fm_file_name, 'filtered_code': curr_new_context_code, 'complete_code': complete_curr_new_context_code}]  # updated context_code after change
                old_context_code = [{'name': new_instance.fm_file_name, 'filtered_code': curr_old_context_code, 'complete_code': complete_curr_old_context_code}]  # original context_code before change
                
                if complete_curr_new_context_code == complete_curr_old_context_code: 
                    logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) is invalid because the context code of the {new_instance.fm_type} `{new_instance.fm_name}` is unchanged.")
                    continue

                if new_instance.fm_file_path == gold_exe_result_dict['fm_file_path']:
                    gold_exe_result = gold_exe_result_dict['exe_result']
                    if gold_exe_result['adapt_grade'] == 0: 
                        logger.print_colored_text(f"Container output:\n{gold_exe_result['exe_result'].stdout}", logger.hex_color_dict['red'])
                    else:
                        logger.print_colored_text(f"Container output:\n{gold_exe_result['exe_result'].stdout}", logger.hex_color_dict['green'])
                    logger.info_with_cyan_background(f"[Unit test summary]")
                    logger.print_colored_text(f"{gold_exe_result['summary']}", logger.hex_color_dict['cyan'])
                else:
                    gold_exe_result = self.filter_via_execution_test(args, new_instance, new_instance.gold_code, new_context_code, True)
                 
                gold_exe_result_dict['fm_file_path'] = new_instance.fm_file_path
                gold_exe_result_dict['exe_result'] = gold_exe_result

                # [Skip current test] Time out
                if gold_exe_result == 'Timeout':
                    return new_filtered_fm_dict_list
                # [Skip current test] pytest filtering
                if gold_exe_result == 'Invalid Test':
                    logger.info(f"[Execution Test for 'gold_code + new_context'] {gold_exe_result}\n")
                    logger.info_with_pink_background(f"[Invalid Test] Skip current unit test file `{test_item['usage_test_file'].split('/')[-1]}` because unit test passed while no unit test executed in this test.")
                    return new_filtered_fm_dict_list
                # [Skip current test] No passed test
                if gold_exe_result['summary']['passed'] == 0: 
                    logger.info(f"[Execution Test for 'gold_code + new_context'] {'Passed' if int(gold_exe_result['adapt_grade']) == 1 else 'Failed'}\n{gold_exe_result['summary']}\n")
                    logger.info_with_pink_background(f"[Invalid Test] Skip current unit test file `{test_item['usage_test_file'].split('/')[-1]}` because no 'passed' unit test in current gold test.")
                    return new_filtered_fm_dict_list
                
                # Print execution test result
                logger.info(f"[Execution Test for 'gold_code + new_context'] {'Passed' if int(gold_exe_result['adapt_grade']) == 1 else 'Failed'}\n")
                # [Skip current test] Check if unit test passed: skip current `test_.py` file if failed
                if gold_exe_result['adapt_grade'] == 0: 
                    logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) is invalid because 'gold_code + new_context_code' failed execution test (which is expected to pass).")
                    return new_filtered_fm_dict_list
                
                original_exe_result = self.filter_via_execution_test(args, new_instance, new_instance.out_of_sync_code, new_context_code, False)
                if original_exe_result == 'Timeout':
                    continue  # move on to the next function/method 
                # [Skip current test] pytest filtering
                if original_exe_result == 'Invalid Test':
                    logger.info(f"[Execution Test for 'original_code + new_context'] {original_exe_result}\n")
                    logger.info_with_pink_background(f"[Invalid Test] Skip current unit test file `{test_item['usage_test_file'].split('/')[-1]}` because unit test passed while no unit test executed in this test.")
                    return new_filtered_fm_dict_list
                # Print execution test result
                logger.info(f"[Execution Test for 'original_code + new_context'] {'Passed' if int(original_exe_result['adapt_grade']) == 1 else 'Failed'}\n")
                # [Skip current test] unittest filtering: if no unit test executed, skip current unit test `test_.py`
                if self.unittest_filtering(args, original_exe_result, gold_exe_result) == False:
                    logger.info_with_pink_background(f"[Invalid Test] Skip current unit test file `{test_item['usage_test_file'].split('/')[-1]}` because unit test passed while no unit test executed in this test.")
                    return new_filtered_fm_dict_list
                
                if original_exe_result['adapt_grade'] == 1:
                    if args.unittest_mode == 'fp':
                        logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) is invalid because 'original_code + new_context_code' passed execution test (which is expected to fail since you choose 'fail-to-pass' only).")
                        continue
                    else:
                        self.test_type = 'pass-to-pass'
                        initial_error_log = original_exe_result['adapt_comment']
                        logger.info_with_green_background(f"[Valid test] Current commit({commit_hash}) is valid for Pass-to-Pass test.")
                else: 
                    if args.unittest_mode == 'pp':
                        logger.info_with_pink_background(f"[Invalid test] Current commit({commit_hash}) is invalid because 'original_code + new_context_code' failed execution test (which is expected to pass since you choose 'pass-to-pass' only).")
                        continue
                    else:
                        self.test_type = 'fail-to-pass'
                        initial_error_log = original_exe_result['adapt_comment']
                        logger.info_with_green_background(f"[Valid test] Current commit({commit_hash}) is valid for Fail-to-Pass test.")

                fm_data_dict = {
                    'fm_type': new_instance.fm_type, 
                    'fm_name': new_instance.fm_name, 
                    'original_code': self.correct_indentation(new_instance.out_of_sync_code),
                    'gold_code': self.correct_indentation(new_instance.gold_code),
                    'code_change_log': generate_code_revision_log(self.correct_indentation(new_instance.out_of_sync_code), self.correct_indentation(new_instance.gold_code))
                }
                old_context_for_curr_fm = self.get_context_code_item(old_context_code, new_instance.fm_file_name)
                new_context_for_curr_fm = self.get_context_code_item(new_context_code, new_instance.fm_file_name)
                context_data_dict = {
                    'pyfile_name': new_instance.fm_file_name, 
                    'old_context_code': old_context_for_curr_fm,
                    'new_context_code': new_context_for_curr_fm,
                    'code_change_log': generate_code_revision_log(old_context_for_curr_fm['filtered_code'], new_context_for_curr_fm['filtered_code'])
                }
                changes_dict = {
                    'dataset': args.dataset, 
                    'test_type': self.test_type,
                    'commit_id': commit_hash,
                    'commit_date': entry['date'],
                    'commit_log': entry['log'],
                    'commit_message': entry['message'],
                    'gold_unittest_log': gold_exe_result['adapt_comment'],
                    'initial_error_log': initial_error_log, 
                    'gold_summary': gold_exe_result['summary'], 
                    'original_summary': original_exe_result['summary'], 
                    'usage_test_file_path': self.relocate_absolute_path_for_exetest(usage_test_file_path),
                    'fm_absolute_path': self.relocate_absolute_path_for_exetest(new_instance.fm_file_path)
                }
                fm_test_dict = {
                    'repo': {'repo_id': fm_dict['repo_id'], 'repo_name': fm_dict['repo_name'], 'repo_url': fm_dict['repo_url']}, 
                    'fm_data': fm_data_dict, 
                    'context_data': context_data_dict,
                    'changes': changes_dict
                }
                new_filtered_fm_dict_list += [fm_test_dict]
                logger.info(f"[Valid test {len(new_filtered_fm_dict_list)+len(self.filtered_fm_dict_list)}/{len(new_filtered_fm_dict_list)+len(self.filtered_fm_dict_list)}] Current commit({commit_hash}) has been successfully recorded.")

                filtered_data_save_path = f"{self.dataset_save_path}callee_{self.repo_id}_{self.repo_name}.json"
                self.save_to_json(self.filtered_fm_dict_list + new_filtered_fm_dict_list, filtered_data_save_path)
                logger.pinfo(f"Current progress successfully saved to '{filtered_data_save_path}'\n")
                logger.info_with_blue_background(f"Current dataset construction progress: {len(self.filtered_fm_dict_list) + len(new_filtered_fm_dict_list)} filtered tests")

                self.logger.collect_log_info(
                    commit_id=commit_hash, 
                    fm_name=new_instance.fm_name, 
                    fm_file=self.relocate_absolute_path_for_exetest(new_instance.fm_file_path), 
                    test_file=self.relocate_absolute_path_for_exetest(usage_test_file_path), 
                    original_exe_result=original_exe_result['exe_result'], 
                    gold_exe_result=gold_exe_result['exe_result'], 
                    test_type=self.test_type
                )
                
        return new_filtered_fm_dict_list
    
    
    def extract_functions_and_methods(self, file_path: str):
        """Extract functions and methods"""
        self.functions, self.methods = [], []
        self.current_file_name = file_path
        self.collect_context_code(file_path)
        
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                self.current_file_content = file.read()
                tree = ast.parse(self.current_file_content, filename=file_path)
                
                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        child.parent = node
                
                self.visit(tree)
        
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                other_encoding_content = file.read()
                self.current_file_content = other_encoding_content.encode('utf-8', errors='ignore').decode('utf-8')
                
                tree = ast.parse(self.current_file_content, filename=file_path)
                
                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        child.parent = node
                
                self.visit(tree)

            
        except SyntaxError as e:
            logger.warning(f"SyntaxError in file {file_path}: {e}")
            return [], []
        
        if self.preprocess_filter_strictness == 1:
            function_filterer = FunctionFilter(self.functions)
            self.functions = function_filterer.function_filtering()
            method_filterer = MethodFilter(self.methods)
            self.methods = method_filterer.method_filtering()
        
        return self.functions, self.methods


    def locate_repo_imports(self, file_path: str):
        """Locate imports"""
        with open(file_path, 'r') as file:
            tree = ast.parse(file.read())

        import_lines = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module
                for alias in node.names:
                    import_lines.append(f"from {module} import {alias.name}")
        return import_lines
    
    
    def find_python_file(self, repo_path: str, relative_path: str):
        for root, dirs, files in os.walk(repo_path):
            potential_path = os.path.join(root, relative_path)
            if os.path.isfile(potential_path):
                return potential_path
        return None
    
    
    def extract_test_objects(self, file_path: str, repo_dir: str):
        import_lines = self.locate_repo_imports(file_path)

        repo_imports = []
        for imp in import_lines:
            parts = imp.split(' ')
            if len(parts) > 1:
                module_path = parts[1].replace('.', os.sep) + '.py'
                file_name = module_path.split(os.sep)[-1]
                relative_path = os.path.join(*module_path.split(os.sep))

                full_path = self.find_python_file(repo_dir, relative_path)
                if file_name == file_path.split('/')[-1]:
                    continue

                if full_path:
                    repo_imports.append({
                        'name': file_name,
                        'file_path': full_path
                    })
                    logger.print_colored_text(f"    -> Found imported dependency `{file_name}` at: {full_path}", logger.hex_color_dict['green'])

        return repo_imports
    
    def remove_duplicates(self, dict_list: List):
        seen = set()
        unique_dicts = []
        for d in dict_list:
            items = tuple(d.items())
            if items not in seen:
                seen.add(items)
                unique_dicts.append(d)
        return unique_dicts
    
    def is_test_file_insensitive(self, filename: str) -> bool:
        """Case-insensitive test file checker"""
        filename = filename.lower()
        return filename.startswith('test') or filename.endswith('test.py')
    
    def check_if_contain_test(self, file_path: str): 
        file_functions, file_methods = self.extract_functions_and_methods(file_path)
        fm_list = file_functions + file_methods
        for fm_dict in fm_list:
            if self.is_test_file_insensitive(fm_dict['name']):
                return True
        return False
    
    def extract_test_objects_from_repo(self, repo_dir: str):
        """Extract tested objects from repo and get covered functions and methods"""
        extracted_test_object_dict_list = []
        processed_dict_list = []
        for root, _, files in os.walk(repo_dir):
            if root != '':
                logger.info(f"Searching directory: {root}")
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)

                        if file_path in processed_dict_list:
                            continue
                        else:
                            processed_dict_list.append(file_path)
                        
                        if self.check_if_contain_test(file_path) == False: 
                            continue

                        extracted_objects = self.remove_duplicates(self.extract_test_objects(file_path, repo_dir))
                        if len(extracted_objects) == 0: 
                            continue
                        for obj in extracted_objects: 
                            if self.dataset_version == 'callee':
                                if obj['name'].startswith('test'):
                                    continue

                            file_functions, file_methods = self.extract_functions_and_methods(obj['file_path'])
                            if len(file_functions+file_methods) == 0: 
                                continue
                            extracted_test_object_dict_list += [{'usage_root_path': root, 'usage_test_file': file_path, 'pyfile_name': obj['name'], 'pyfile_path': obj['file_path'], 'fms': file_functions+file_methods}]
            
            # Stop data extraction if reach raw-data max length
            if len(extracted_test_object_dict_list) > self.max_extracted_data_to_be_filtered:
               break
        return extracted_test_object_dict_list
    
    def extract_fm_from_in_test_object(self, args, repo_dir: str):
        # (1) Extract test objects
        potential_saved_path = f"{args.root_path}{args.dataset_path}{self.repo_id}_{self.repo_name}_extracted_test_object_dict_list.json"
        if os.path.exists(potential_saved_path): 
            logger.info(f"Find `extracted_test_object_dict_list` exists at '{potential_saved_path}', which use the existing `extracted_test_object_dict_list` directly")
            extracted_test_object_dict_list = read_test_data(potential_saved_path)
        else: 
            logger.info(f"No existing `extracted_test_object_dict_list` at '{potential_saved_path}'. Starting extraction...")
            extracted_test_object_dict_list = self.extract_test_objects_from_repo(repo_dir)
            logger.pinfo("Extraction success!\n")

        # (2) Get git log
        self.get_current_git_log(args)

        # (3) Filter extracted functions & methods
        print_filter_progress = 0
        for test_item in extracted_test_object_dict_list:
            print_filter_progress += 1
            logger.print_colored_text(f"\n{'=' * 160}", logger.hex_color_dict['cyan'])
            logger.print_colored_text(f"{' ' * 55} Multi-level Filtering {print_filter_progress}/{len(extracted_test_object_dict_list)}: [{test_item['usage_test_file'].split('/')[-1]}]", logger.hex_color_dict['cyan'])
            logger.print_colored_text(f"{'=' * 160}\n", logger.hex_color_dict['cyan'])
            self.filtered_fm_dict_list += self.fm_filtering(args, test_item)
            
            if len(self.filtered_fm_dict_list) > 0:
                self.save_to_json(self.filtered_fm_dict_list, f"{self.dataset_save_path}callee_{self.repo_id}_{self.repo_name}.json")
        
        # Temporary files removal
        instance_info = {
            'repo_id': self.repo_id, 
            'repo_name': self.repo_name
        }
        instance = InstanceConfig(**instance_info)
        exe_tester = SandBoxManager(args, instance, None, None)
        
        if args.unittest_exetest_method == 0: 
            exe_tester.remove_after_execution_test()
        else: 
            if args.remove_image_after_use:
                exe_tester.remove_docker_image()
                
        self.clean_remove_dir(self.clone_dir)
        self.clean_remove_dir(self.code_path)
        self.save_to_json(self.filtered_fm_dict_list, f"{self.dataset_save_path}callee_{self.repo_id}_{self.repo_name}.json")
        return self.filtered_fm_dict_list
    