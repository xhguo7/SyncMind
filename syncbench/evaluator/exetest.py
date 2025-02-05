"""
Execution test
"""

import os
import subprocess
import shutil
import re
import git
import autopep8
from syncbench.utilizer.aligner import align_agent_context
from syncbench.evaluator.handler import DockerHandler
from utils.logger import logger


class ExecutionTest(object):
    """Execution test class"""
    def __init__(self, args, instance, agent_revised_code, corresponding_context_code):
        # Unit test
        self.test_method = args.env_test_method
        self.env_additional_unittest_command = args.env_additional_unittest_command
        self.python_version = args.env_python_version
        self.usage_test_file_path = instance.usage_test_file_path
        # Repo
        self.repo_url = instance.repo_url
        self.fm_name = instance.fm_name
        self.fm_file_name = instance.fm_file_name
        self.pyfile_name_list = instance.python_file_list + ["agent_code.py", "context_code.py"] if instance.python_file_list else ["agent_code.py", "context_code.py"]
        self.agent_revised_code = self.correct_indentation(agent_revised_code)
        self.context_code = corresponding_context_code
        # Path
        self.test_path = f"{args.root_path}{args.code_path}"
        self.code_path = f"{args.root_path}{args.code_path}"
        self.venv_path = f"{args.root_path}{args.code_path}test_venv/"
        self.repo_path = f"{args.root_path}{args.code_path}test_repo/"
        self.agent_code_path = instance.fm_file_path  # pyfile path of current fm
        

    def correct_indentation(self, code: str) -> str:
        """Python code format correction"""
        try:
            corrected_code = autopep8.fix_code(code, options={'indent_size': 4})
            return corrected_code
        except Exception as e:
            return code
    
    def run_command(self, command, cwd=None, env=None):
        """Run a shell command"""
        result = subprocess.run(command, shell=True, cwd=cwd, env=env, capture_output=True, text=True)
        return result

    def create_venv(self):
        """Create virtual environment"""
        logger.info("Constructing test venv...")
        activate_path = os.path.join(self.venv_path, 'bin', 'activate')
        if not os.path.exists(activate_path):
            logger.pinfo(f"    Virtual environment not found at {self.venv_path}. Creating a new one...")
            subprocess.run([self.python_version, "-m", "venv", self.venv_path], check=True)
            logger.pinfo("    Virtual environment created.")
            return 1
        else:
            logger.pinfo(f"    Virtual environment already exists at {self.venv_path}. Skipping creation.")
            return 0
        
    def create_requirements_txt(self, args):
        requirements_file = os.path.join(self.repo_path, 'requirements.txt')
        with open(requirements_file, 'w') as file:
            file.write(args.env_requirements)  # TODO [venv] modify your default env
    
    def capture_package_in_line(self, inputstr):
        inputstr = inputstr.replace(' ', '')
        match = re.match(r'^[a-zA-Z]+', inputstr)
        if match:
            return match.group(0)
        return inputstr
    
    def install_requirements(self, requirements_file):
        """Install requirements from requirements.txt into the virtual environment"""
        pip_path = os.path.join(self.venv_path, 'bin', 'pip') if os.name != 'nt' else os.path.join(self.venv_path, 'Scripts', 'pip')
        with open(requirements_file, 'r') as file:
            for line in file:
                package = line.strip()
                if package:
                    logger.info(f"Installing: {package}")
                    if not self.install_package(pip_path, package):
                        package_name = self.capture_package_in_line(package)
                        latest_package = package_name.strip()
                        logger.pinfo(f"Installing '{package}' failed, try to reinstall the latest version of '{latest_package}'")
                        self.install_package(pip_path, latest_package)
                    else: 
                        logger.pinfo(f"Successfully installed '{package}'")
    
    def install_package(self, pip_path, package):
        install_command = f"{pip_path} install {package}"
        try:
            result = subprocess.run(install_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.info(result.stdout.decode())
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to install {package}: {e.stderr.decode()}")
            return False
        
    def env_install_with_command(self, install_command):
        logger.info(f"Installing via command `{install_command}`")
        try:
            result = subprocess.run(install_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.pinfo(result.stdout.decode())
            return True
        except subprocess.CalledProcessError as e:
            logger.pinfo(f"Failed to install via `{install_command}`: {e.stderr.decode()}")
            return False
    
    def execute_test_code(self):
        """Execution test"""
        python_path = os.path.join(self.venv_path, 'bin', 'python') if os.name != 'nt' else os.path.join(self.venv_path, 'Scripts', 'python')
        relative_path = self.usage_test_file_path.split('test_repo/')[1]
        run_commands = [
            f"{self.venv_path}bin/pip install --upgrade pip", 
            f"{python_path} -m pip install -e . ", 
            f"{python_path} -m {self.test_method} -v {relative_path} " + f"{self.env_additional_unittest_command} "
        ]
        for comm in run_commands:
            exe_result = self.run_command(comm, cwd=self.repo_path)
        logger.info(f"Execution test output:\n{exe_result.stdout}\n")
        return exe_result
    
    def remove_after_execution_test(self):
        """Remove repo and venv after execution test"""
        self.clean_directory_removal(self.venv_path)
        logger.info('Temporary test_venv of current execution test has been successfully removed.\n')
        
        self.clean_directory_removal(self.code_path)
        logger.pinfo('Temporary code_path of current execution test has been successfully removed.\n')
    
    
    def clean_directory_removal(self, target_dir):
        """Remove repo - strict removal"""
        for root, dirs, files in os.walk(target_dir, topdown=False):
            for name in files:
                file_path = os.path.join(root, name)
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Failed to remove file {file_path}: {e}\nAttempting to remove file {file_path} again...")

            for name in dirs:
                dir_path = os.path.join(root, name)
                try:
                    os.rmdir(dir_path)
                except Exception as e:
                    logger.warning(f"Failed to remove directory `{dir_path}`: {e}\nAttempting to remove directory `{dir_path}` again...")

        try:
            shutil.rmtree(target_dir, ignore_errors=True)
            logger.info(f"Successfully removed target directory at `{target_dir}`")

        except Exception as e:
            logger.warning(f"Failed to remove target directory at `{target_dir}`: {e}\nAttempting to remove directory `{target_dir}` again...")
            self.clean_directory_removal(target_dir)
    

    def remove_all_pyfiles(self):
        """Remove all python files used in current execution test"""
        logger.info(f"Removing all Python code files used in current execution test...")
        for pyfile in self.pyfile_name_list:
            pyfile_path = os.path.join(self.code_path, pyfile)
            try:
                if os.path.exists(pyfile_path):
                    os.remove(pyfile_path)
                    logger.pinfo(f"    Removed: {pyfile} saved at `{pyfile_path}`")
                else:
                    logger.pinfo(f"    File not found: {pyfile} expected to be saved at `{pyfile_path}`")
            except Exception as e:
                logger.warning(f"    Error removing {pyfile}: {e}")
        logger.pinfo(f"Removed all Python code files used in current execution test.")

    def clone_repository(self):
        """Clone repo"""
        if os.path.exists(self.repo_path) and os.path.isdir(self.repo_path):
            try:
                repo = git.Repo(self.repo_path)
                if not repo.bare:
                    logger.info(f"Repository already cloned at `{self.repo_path}`. Skipping clone.")
                    return
            except git.exc.InvalidGitRepositoryError:
                logger.warning(f"`{self.repo_path}` is not a valid Git repository. Re-cloning.")
                shutil.rmtree(self.repo_path)
        else:
            os.makedirs(self.repo_path, exist_ok=True)
            git.Repo.clone_from(self.repo_url, self.repo_path)
            logger.info(f"Repository cloned to `{self.repo_path}`.")
    
    def clone_repository_from_image(self, dest_path: str=None, force_remove: bool=False):
        """Clone repo from docker image"""
        if not dest_path:
            dest_path = self.repo_path

        if os.path.exists(dest_path) and os.path.isdir(dest_path):
            logger.info(f"Repository already exists at `{dest_path}`.")
            if force_remove:
                logger.pinfo(f"Removing existing repo and re-cloning...")
                self.clean_directory_removal(dest_path)
            else:
                logger.pinfo(f"Skipping repo clone...")
                return
                
        try:
            docker_handler = DockerHandler(self.image_name_with_tag, dest_path)
            docker_handler.all_in_one_run_copy_remove_container()
            logger.info(f"Repository cloned from docker image to `{dest_path}`")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository from docker image: {e}")
        
        
    def add_pytest_package(self, requirements_file):
        with open(requirements_file, 'a+') as file:
            file.write('\npytest')

    def execution_test(self, args):
        """Execution test validation"""
        self.clone_repository()
        self.save_code_to_file()
        
        try:
            if_newly_created = self.create_venv()
            if if_newly_created == 1:
                general_installs = [
                    f"{self.venv_path}bin/pip install --upgrade pip", 
                    f"{self.venv_path}bin/pip install -y git curl", 
                    f"{self.venv_path}bin/pip install -y ninja-build", 
                    f"{self.venv_path}bin/pip install flit", 
                    f"{self.venv_path}bin/pip install --upgrade setuptools", 
                    f"{self.venv_path}bin/pip install -U pytest-asyncio"
                ]
                for install_item in general_installs:
                    self.env_install_with_command(install_item)

                # If have args.env_requirements
                if args.env_requirements != []:  # Install dependencies from my_repo_dict[repo_idx]['requirements']
                    for item in args.env_requirements:
                        if ("==" in item) or (">=" in item) or ("<=" in item):
                            install_command_item = f"{self.venv_path}bin/pip install {item.replace(' ', '')}"
                        else: 
                            install_command_item = f"{self.venv_path}bin/pip install {item}"
                        self.env_install_with_command(install_command_item)
                # If have args.env_install_command
                elif args.env_install_command != []:  # Install dependencies from my_repo_dict[repo_idx]['install_command']
                    for install_command_item in args.env_install_command:
                        install_command = self.venv_path + 'bin/' + install_command_item
                        self.env_install_with_command(install_command)
                
                # Repo setup installs
                repo_setup_installs = [
                    f"if [ -f pyproject.toml ]; then "
                    f". {self.venv_path}bin/activate && "
                    f"curl -sSL https://install.python-poetry.org | python3 - && "
                    f"export PATH=$PATH:/root/.local/bin && "
                    f"grep -q '[tool.poetry]' pyproject.toml && /root/.local/bin/poetry install || "
                    f"{self.venv_path}bin/pip install .; "
                    f"elif [ -f setup.py ]; then "
                    f". {self.venv_path}bin/activate && pip install .; "
                    f"else "
                    f"echo 'No pyproject.toml or setup.py found, skipping dependency installation'; "
                    f"fi"
                ]
                for install_item in repo_setup_installs:
                    self.env_install_with_command(install_item)

            logger.info("    Dependencies are successfully installed. \nStart execution test...\n")

            # Execution test
            execution_test_result = {}
            exe_result = self.execute_test_code()
            if exe_result.returncode == 0:
                execution_test_result['adapt_grade'] = 1
                execution_test_result['adapt_comment'] = exe_result.stdout
                execution_test_result['exe_result'] = exe_result
                return execution_test_result
            else:
                execution_test_result['adapt_grade'] = 0
                execution_test_result['adapt_comment'] = exe_result.stdout
                execution_test_result['exe_result'] = exe_result
                return execution_test_result
        finally:
            self.clean_directory_removal(self.repo_path)
            

    def ensure_path_exists(self, dir_path):
        if os.path.exists(dir_path):
            logger.info(f"The path '{dir_path}' already exists.")
            return
    
        if os.path.splitext(dir_path)[1]:
            os.makedirs(os.path.dirname(dir_path), exist_ok=True)
        else:
            os.makedirs(dir_path, exist_ok=True)
    
        logger.info(f"The path '{dir_path}' has been created.")

    def save_code_to_file(self):
        for context_idx in range(len(self.context_code)):
            if self.fm_file_name == self.context_code[context_idx]['name']:
                self.agent_revised_code = align_agent_context(self.agent_revised_code, self.context_code[context_idx]['complete_code'])
                
                # Check if path exists
                self.ensure_path_exists(self.agent_code_path)

                with open(self.agent_code_path, 'w') as file:
                    file.write(self.agent_revised_code)
