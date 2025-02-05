"""
Filtering methods for dataset construction
"""

import ast
from typing import List, Dict
from syncbench.utilizer.function_filter import FunctionFilter

class MethodFilter(FunctionFilter):
    def __init__(self, methods: List[Dict]):
        super().__init__(methods)
    
    def method_filtering(self) -> List[Dict]:
        filtered_methods = []
        # Use 'functions' attribute from FunctionFilter
        for method in self.functions:
            if not self._is_valid_method(method):
                continue
            filtered_methods.append(method)
        return filtered_methods
    
    # Method filtering
    def _is_valid_method(self, method: Dict) -> bool:
        # Parse the method code to get the AST node
        method_node = self._get_method_node(method['code'])
        if method_node is None:
            return False

        # Apply all function-level filters using the parsed AST node
        if not self._is_valid_function_node(method, method_node):
            return False

        # Filter out methods that are not part of a class
        if not self._is_method_in_class(method['context'], method['name']):
            return False

        # Additional example filtering logic specific to methods
        if method['name'].startswith('__'):
            return False

        return True

    def _is_valid_function_node(self, method: Dict, method_node: ast.FunctionDef) -> bool:
        # Filter out methods with zero arguments
        if self.get_num_arguments(method_node) == 0:
            return False

        # Filter out methods with no return statements
        if not any(isinstance(node, ast.Return) for node in method_node.body):
            return False

        # Filter out methods with literal return values
        if self.has_literal_return(method_node):
            return False

        # Filter out methods without a docstring
        if ast.get_docstring(method_node) is None:
            return False

        # Filter out methods with bad names
        if method['name'] in {"test", "temp", "sample"}:
            return False

        # Additional example filtering logic
        if len(method['code'].splitlines()) <= 5:
            return False

        return True

    def _get_method_node(self, code: str) -> ast.FunctionDef:
        try:
            tree = ast.parse(code)
            for node in tree.body:
                if isinstance(node, ast.FunctionDef):
                    return node
        except SyntaxError:
            return None
        return None

    def _is_method_in_class(self, context: List[Dict], method_name: str) -> bool:
        for context_item in context:
            try:
                tree = ast.parse(context_item['code'])
                for node in tree.body:
                    if isinstance(node, ast.ClassDef):
                        for class_node in node.body:
                            if isinstance(class_node, ast.FunctionDef) and class_node.name == method_name:
                                return True
            except SyntaxError:
                continue
        return False
