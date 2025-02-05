"""
Instances
"""

import ast
import astor
import difflib
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class InstanceConfig:
    fm_type: str = None
    fm_name: str = None
    fm_file_name: str = None
    python_file_list: List = None
    gold_code: str = None
    out_of_sync_code: str = None
    old_context_code: List = None
    new_context_code: List = None
    fm_context_dict: Dict = None
    fm_file_path: str = None
    usage_test_file_path: str = None
    repo_id: str = None
    repo_name: str = None
    repo_url: str = None

def remove_fm_in_context_code(function_name: str, source_code: str) -> str:
    class FunctionRemover(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            if node.name == function_name:
                return None
            return node
            
        def visit_ClassDef(self, node):
            # Keep the class but check its methods
            node.body = [
                method for method in node.body 
                if not (isinstance(method, ast.FunctionDef) and method.name == function_name)
            ]
            return node if node.body else None
    
    tree = ast.parse(source_code)
    transformer = FunctionRemover()
    modified_tree = transformer.visit(tree)
    return astor.to_source(modified_tree)

def generate_code_revision_log(original_code: str, revised_code: str) -> str:
    # Split the original and revised code into lines
    original_lines = original_code.splitlines()
    revised_lines = revised_code.splitlines()
    
    # Use difflib to get the differences
    diff = difflib.unified_diff(original_lines, revised_lines, lineterm='')
    
    # Generate the log
    log = '\n'.join(diff)
    
    return log

