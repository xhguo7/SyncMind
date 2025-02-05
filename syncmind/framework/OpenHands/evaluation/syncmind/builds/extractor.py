"""
Function utils
"""

import os
import ast
from openhands.core.logger import openhands_logger as logger
from evaluation.syncmind.builds.aligner import correct_indentation


def save_python_code_to_file(code_content: str, file_path: str) -> None:
    """
    Save Python code content to a local file in UTF-8 encoding.

    Args:
        code_content (str): The Python code to save.
        file_path (str): The path to the file where the code will be saved.
    """
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(code_content)


def read_python_code_from_file(file_path: str) -> str:
    """
    Read Python code content from a local file in UTF-8 encoding.

    Args:
        file_path (str): The path to the file to read the code from.

    Returns:
        str: The Python code content read from the file.
    """
    with open(file_path, 'r', encoding='utf-8') as file:
        code_content = file.read()
    return code_content


def extract_function_code(updated_code: str, fm_name: str) -> str:
    """
    Extract the entire function/method code content from a Python file.
    
    Args:
        updated_code (str): The entire code content of agent's updated Python file.
        fm_name (str): The name of the function/method to extract.
    
    Returns:
        str: The code content of the specified function/method.
    """
    if not updated_code:
        logger.info("Agent did not update responsible code.")
        return None

    try:
        tree = ast.parse(updated_code)
    except SyntaxError as e:
        logger.exception(f"Agent's updated code has SyntaxError: {e}")
        return None
    except Exception as e:
        logger.exception(f"Agent's updated code has Exception: {e}")
        return None
    
    class FunctionVisitor(ast.NodeVisitor):
        def __init__(self, fm_name):
            self.fm_name = fm_name
            self.code_content = None
            
        def visit_FunctionDef(self, node):
            if node.name == self.fm_name:
                self.code_content = ast.get_source_segment(updated_code, node)
        
        def visit_AsyncFunctionDef(self, node):
            if node.name == self.fm_name:
                self.code_content = ast.get_source_segment(updated_code, node)

    visitor = FunctionVisitor(fm_name)
    visitor.visit(tree)

    if visitor.code_content:
        return correct_indentation(visitor.code_content.strip())
    else:
        logger.info(f"Function/method '{fm_name}' not found in agent's revised code file.")
        return None
    
