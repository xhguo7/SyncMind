"""
Filtering functions for SyncBench construction
"""

import ast
from typing import List, Dict
from utils.logger import logger

class FunctionFilter(object):
    def __init__(self, functions: List[Dict]):
        self.functions = functions
    
    def function_filtering(self) -> List[Dict]:
        filtered_functions = []
        for func in self.functions:
            if not self._is_valid_function(func):
                continue
            filtered_functions.append(func)
        return filtered_functions
    
    # Function filtering
    def _is_valid_function(self, function: Dict) -> bool:
        # Parse the function code to get the AST node
        function_node = self._get_function_node(function['code'])
        if function_node is None:
            return False

        # Filter out functions with zero arguments
        if self.get_num_arguments(function_node) == 0:
            return False

        # Filter out functions with no return statements
        if not any(isinstance(node, ast.Return) for node in function_node.body):
            return False

        # Filter out functions with literal return values
        if self.has_literal_return(function_node):
            return False

        # Filter out functions without a docstring
        if ast.get_docstring(function_node) is None:
            return False

        # Filter out functions with bad names (e.g., "test", "temp", or "sample")
        if function['name'] in {"test", "temp", "sample"}:
            return False

        # Filter out functions that are 5 lines or shorter
        if len(function['code'].splitlines()) <= 5:
            return False

        return True

    def _get_function_node(self, code: str) -> ast.FunctionDef:
        try:
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    return node
        except SyntaxError:
            # Log the syntax error and move on to the next function
            logger.warning(f"SyntaxError in code:\n{code}")
            return None
        return None

    def get_num_arguments(self, function_node: ast.FunctionDef) -> int:
        return (
            len(function_node.args.args) +
            len(function_node.args.kwonlyargs) +
            len(function_node.args.posonlyargs) +
            (0 if function_node.args.kwarg is None else 1) +
            (0 if function_node.args.vararg is None else 1)
        )

    def has_literal_return(self, function_node: ast.FunctionDef) -> bool:
        def is_literal(node):
            # Check if the node is a Constant (handles str, num, bool, None)
            if isinstance(node, ast.Constant):
                return True
                
            # Handle complex numbers (real + imag) if needed
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                return (isinstance(node.left, ast.Constant) and 
                    isinstance(node.right, ast.Constant))
                
            return False
            
        for node in ast.walk(function_node):
            if isinstance(node, ast.Return) and node.value is not None:
                if is_literal(node.value):
                    return True
                    
        return False
