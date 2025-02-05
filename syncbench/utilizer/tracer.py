"""
Trace commits for each function/method
"""

import git
import os
import ast
import autopep8
from textwrap import dedent
from utils.logger import logger

class CodeHistoryTracer:
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir
        self.repo = git.Repo(repo_dir)

    
    def correct_indentation(self, code: str) -> str:
        """Python code format correction"""
        try:
            corrected_code = autopep8.fix_code(code, options={'indent_size': 4})
            return corrected_code
        except Exception as e:
            logger.warning(f"[Invalid Code Format Correction] An error occurred:\n{e}\nDirectly returning original code...")
            return code
    
    
    def get_function_history(self, file_path, function_name):
        """Trace the history of a specific function/method"""
        file_rel_path = os.path.relpath(file_path, self.repo_dir)
        commits = list(self.repo.iter_commits(paths=file_rel_path))
        history = []
        for commit in commits:
            self.checkout_commit(commit)
            code = self.get_function_code_at_commit(file_rel_path, function_name)
            if code:
                log_content = self.repo.git.show(commit)
                history.append({
                    "log": log_content,
                    "commit": commit.hexsha,
                    "message": commit.message,
                    "author": commit.author.name,
                    "date": str(commit.committed_datetime),
                    "code": self.correct_indentation(code)
                })

        self.checkout_main_branch()
        return history
    
    
    def checkout_commit(self, commit):
        """Safely checkout to a specific commit"""
        try:
            self.repo.git.reset('--hard')
            self.repo.git.checkout(commit)
        except git.exc.GitCommandError as e:
            logger.warning(f"Error during checkout: {e}\nSkipping current commit checkout...")
    

    def checkout_main_branch(self):
        """Return to the main or master branch and apply stashed changes"""
        try:
            branch_name = "main" if "main" in self.repo.heads else "master"
            self.repo.git.checkout(branch_name)
            self.repo.git.reset('--hard')
            if self.repo.git.stash('list'):
                self.repo.git.stash('pop')
        except git.exc.GitCommandError as e:
            logger.warning(f"Error during checkout: {e}\nSkipping current commit checkout...")
    

    def get_function_code_at_commit(self, file_rel_path, function_name):
        """Get the function/method code from a specific commit"""
        file_path = os.path.join(self.repo_dir, file_rel_path)
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()

        try:
            tree = ast.parse(file_content)
        except (SyntaxError, IndentationError) as e:
            logger.warning(f"Skipping commit due to parsing error: {e}")
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == function_name:
                return dedent(ast.get_source_segment(file_content, node))
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, ast.FunctionDef) and child.name == function_name:
                        return dedent(ast.get_source_segment(file_content, child))
        return None
    
    
    def restore_function_code(self, file_path, function_name, commit_hash):
        """Restore the function/method code to a specific version"""
        self.checkout_commit(commit_hash)
        file_rel_path = os.path.relpath(file_path, self.repo_dir)
        restored_code = self.get_function_code_at_commit(file_rel_path, function_name)
        self.checkout_main_branch()
        return self.correct_indentation(restored_code)
    
    
    def get_file_history(self, file_path):
        """Trace the history of a Python file"""
        file_rel_path = os.path.relpath(file_path, self.repo_dir)
        commits = list(self.repo.iter_commits(paths=file_rel_path))
        history = []
        for commit in commits:
            self.checkout_commit(commit)
            code = self.get_file_code_at_commit(file_rel_path)
            if code:
                log_content = self.repo.git.show(commit)
                history.append({
                    "log": log_content,
                    "commit": commit.hexsha,
                    "message": commit.message,
                    "author": commit.author.name,
                    "date": str(commit.committed_datetime),
                    "code": code
                })

        self.checkout_main_branch()
        return history
    
    
    def get_file_code_at_commit(self, file_rel_path):
        """Get the entire file code from a specific commit"""
        file_path = os.path.join(self.repo_dir, file_rel_path)
        if not os.path.exists(file_path):
            return None

        with open(file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()

        try:
            return dedent(file_content)
        except (SyntaxError, IndentationError) as e:
            logger.warning(f"Skipping commit due to parsing error: {e}")
            return None
    
    
    def restore_file_code(self, file_path, commit_hash):
        """Restore the entire file code to a specific version at a specific commit"""
        self.checkout_commit(commit_hash)
        file_rel_path = os.path.relpath(file_path, self.repo_dir)
        restored_code = self.get_file_code_at_commit(file_rel_path)
        self.checkout_main_branch()
        return self.correct_indentation(restored_code)
