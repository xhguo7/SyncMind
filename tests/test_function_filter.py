"""
Unit test on function filtering
"""

import pytest
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from syncbench.utilizer.function_filter import FunctionFilter

# Sample functions for testing
VALID_FUNCTION = {
    'name': 'process_data',
    'code': '''
def process_data(data, config=None):
    """
    Process the input data according to the configuration.
    
    Args:
        data: Input data to process
        config: Configuration dictionary
    
    Returns:
        Processed data
    """
    result = []
    for item in data:
        if config and item in config:
            result.append(config[item])
        else:
            result.append(item)
    return result
'''
}

NO_ARGS_FUNCTION = {
    'name': 'get_constant',
    'code': '''
def get_constant():
    """Returns a constant value."""
    return 42
'''
}

NO_RETURN_FUNCTION = {
    'name': 'print_data',
    'code': '''
def print_data(data):
    """Print the input data."""
    print(data)
'''
}

LITERAL_RETURN_FUNCTION = {
    'name': 'return_literal',
    'code': '''
def return_literal(x):
    """Return a literal value."""
    return 42
'''
}

NO_DOCSTRING_FUNCTION = {
    'name': 'process',
    'code': '''
def process(data):
    return data.upper()
'''
}

BAD_NAME_FUNCTION = {
    'name': 'test',
    'code': '''
def test(data):
    """Test function."""
    return data.process()
'''
}

SHORT_FUNCTION = {
    'name': 'short',
    'code': '''
def short(x):
    """Short function."""
    return x + 1
'''
}

INVALID_SYNTAX_FUNCTION = {
    'name': 'invalid',
    'code': '''
def invalid(x)
    return x
'''
}

@pytest.fixture
def function_filter():
    return FunctionFilter([])

def test_valid_function(function_filter):
    filter_instance = FunctionFilter([VALID_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 1
    assert filtered[0]['name'] == 'process_data'

def test_no_args_function(function_filter):
    filter_instance = FunctionFilter([NO_ARGS_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_no_return_function(function_filter):
    filter_instance = FunctionFilter([NO_RETURN_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_literal_return_function(function_filter):
    filter_instance = FunctionFilter([LITERAL_RETURN_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_no_docstring_function(function_filter):
    filter_instance = FunctionFilter([NO_DOCSTRING_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_bad_name_function(function_filter):
    filter_instance = FunctionFilter([BAD_NAME_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_short_function(function_filter):
    filter_instance = FunctionFilter([SHORT_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_invalid_syntax_function(function_filter):
    filter_instance = FunctionFilter([INVALID_SYNTAX_FUNCTION])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0

def test_multiple_functions():
    functions = [
        VALID_FUNCTION,
        NO_ARGS_FUNCTION,
        NO_RETURN_FUNCTION,
        LITERAL_RETURN_FUNCTION,
        NO_DOCSTRING_FUNCTION,
        BAD_NAME_FUNCTION,
        SHORT_FUNCTION,
        INVALID_SYNTAX_FUNCTION
    ]
    filter_instance = FunctionFilter(functions)
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 1
    assert filtered[0]['name'] == 'process_data'

def test_get_num_arguments():
    filter_instance = FunctionFilter([])
    function_node = filter_instance._get_function_node(VALID_FUNCTION['code'])
    assert filter_instance.get_num_arguments(function_node) == 2

def test_has_literal_return():
    filter_instance = FunctionFilter([])
    literal_node = filter_instance._get_function_node(LITERAL_RETURN_FUNCTION['code'])
    assert filter_instance.has_literal_return(literal_node) == True
    
    non_literal_node = filter_instance._get_function_node(VALID_FUNCTION['code'])
    assert filter_instance.has_literal_return(non_literal_node) == False

def test_empty_function_list():
    filter_instance = FunctionFilter([])
    filtered = filter_instance.function_filtering()
    assert len(filtered) == 0
    assert isinstance(filtered, list)
