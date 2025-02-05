"""
Unit test on method filtering
"""

import ast
import pytest
import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from syncbench.utilizer.method_filter import MethodFilter


# Sample class definitions that will be used as context
CLASS_WITH_METHODS = {
    'code': '''
class DataProcessor:
    def process_data(self, data, config=None):
        """Process the input data according to configuration."""
        result = []
        for item in data:
            if config and item in config:
                result.append(config[item])
            else:
                result.append(item)
        return result

    @property
    def config_status(self):
        """Get configuration status."""
        return bool(self._config)

    @staticmethod
    def validate_data(data):
        """Validate input data."""
        return len(data) > 0

    @classmethod
    def from_config(cls, config):
        """Create instance from config."""
        return cls(config)
'''
}

# Valid regular instance method
VALID_METHOD = {
    'name': 'process_data',
    'code': '''
def process_data(self, data, config=None):
    """Process the input data according to configuration."""
    result = []
    for item in data:
        if config and item in config:
            result.append(config[item])
        else:
            result.append(item)
    return result''',
    'context': [CLASS_WITH_METHODS]
}

# Valid property method
VALID_PROPERTY = {
    'name': 'config_status',
    'code': '''
@property
def config_status(self):
    """Get configuration status."""
    return bool(self._config)''',
    'context': [CLASS_WITH_METHODS]
}

# Valid static method
VALID_STATIC_METHOD = {
    'name': 'validate_data',
    'code': '''
@staticmethod
def validate_data(data):
    """Validate input data."""
    return len(data) > 0''',
    'context': [CLASS_WITH_METHODS]
}

# Valid class method
VALID_CLASS_METHOD = {
    'name': 'from_config',
    'code': '''
@classmethod
def from_config(cls, config):
    """Create instance from config."""
    return cls(config)''',
    'context': [CLASS_WITH_METHODS]
}

# Method without class context
NO_CLASS_CONTEXT_METHOD = {
    'name': 'process_data',
    'code': VALID_METHOD['code'],
    'context': []
}

# Dunder method
DUNDER_METHOD = {
    'name': '__init__',
    'code': '''
def __init__(self, config):
    """Initialize with config."""
    self.config = config
    return None''',
    'context': [CLASS_WITH_METHODS]
}

# Method with no arguments
NO_ARGS_METHOD = {
    'name': 'get_default',
    'code': '''
def get_default():
    """Get default value."""
    return "default"''',
    'context': [CLASS_WITH_METHODS]
}

# Method with no return statement
NO_RETURN_METHOD = {
    'name': 'print_data',
    'code': '''
def print_data(self, data):
    """Print the input data."""
    print(data)''',
    'context': [CLASS_WITH_METHODS]
}

# Method with literal return
LITERAL_RETURN_METHOD = {
    'name': 'get_constant',
    'code': '''
def get_constant(self):
    """Return a constant value."""
    return 42''',
    'context': [CLASS_WITH_METHODS]
}

# Method without docstring
NO_DOCSTRING_METHOD = {
    'name': 'transform',
    'code': '''
def transform(self, data):
    return data.upper()''',
    'context': [CLASS_WITH_METHODS]
}

# Method with bad name
BAD_NAME_METHOD = {
    'name': 'test',
    'code': '''
def test(self, data):
    """Test method."""
    return data.process()''',
    'context': [CLASS_WITH_METHODS]
}

# Short method
SHORT_METHOD = {
    'name': 'short',
    'code': '''
def short(self, x):
    """Short."""
    return x''',
    'context': [CLASS_WITH_METHODS]
}

# Method with invalid syntax
INVALID_SYNTAX_METHOD = {
    'name': 'invalid',
    'code': '''
def invalid(self, x)
    return x''',
    'context': [CLASS_WITH_METHODS]
}

# Private method
PRIVATE_METHOD = {
    'name': '_private_helper',
    'code': '''
def _private_helper(self, data):
    """Private helper method."""
    return self.process_data(data)''',
    'context': [CLASS_WITH_METHODS]
}

@pytest.fixture
def method_filter():
    return MethodFilter([])

def test_valid_instance_method():
    """Test that valid instance methods are accepted."""
    filter_instance = MethodFilter([VALID_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 1
    assert filtered[0]['name'] == 'process_data'

def test_valid_property_method():
    """Test that property methods are filtered out (they often don't have explicit returns)."""
    filter_instance = MethodFilter([VALID_PROPERTY])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0  # Properties should be filtered out

def test_valid_static_method():
    """Test that static methods are filtered out (no self parameter)."""
    filter_instance = MethodFilter([VALID_STATIC_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0  # Static methods should be filtered out

def test_valid_class_method():
    """Test that class methods are filtered out (uses cls instead of self)."""
    filter_instance = MethodFilter([VALID_CLASS_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0  # Class methods should be filtered out

def test_no_class_context():
    """Test that methods without class context are filtered out."""
    filter_instance = MethodFilter([NO_CLASS_CONTEXT_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_dunder_method():
    """Test that dunder methods are filtered out."""
    filter_instance = MethodFilter([DUNDER_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_no_args_method():
    """Test that methods with no arguments are filtered out."""
    filter_instance = MethodFilter([NO_ARGS_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_no_return_method():
    """Test that methods with no return statement are filtered out."""
    filter_instance = MethodFilter([NO_RETURN_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_literal_return_method():
    """Test that methods with literal returns are filtered out."""
    filter_instance = MethodFilter([LITERAL_RETURN_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_no_docstring_method():
    """Test that methods without docstrings are filtered out."""
    filter_instance = MethodFilter([NO_DOCSTRING_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_bad_name_method():
    """Test that methods with bad names are filtered out."""
    filter_instance = MethodFilter([BAD_NAME_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_short_method():
    """Test that short methods are filtered out."""
    filter_instance = MethodFilter([SHORT_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_invalid_syntax_method():
    """Test that methods with invalid syntax are filtered out."""
    filter_instance = MethodFilter([INVALID_SYNTAX_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0

def test_private_method():
    """Test that private methods are filtered out."""
    filter_instance = MethodFilter([PRIVATE_METHOD])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0  # Private methods should be filtered out

def test_multiple_methods():
    """Test filtering of multiple methods at once."""
    methods = [
        VALID_METHOD,
        VALID_PROPERTY,
        VALID_STATIC_METHOD,
        VALID_CLASS_METHOD,
        NO_CLASS_CONTEXT_METHOD,
        DUNDER_METHOD,
        NO_ARGS_METHOD,
        NO_RETURN_METHOD,
        LITERAL_RETURN_METHOD,
        NO_DOCSTRING_METHOD,
        BAD_NAME_METHOD,
        SHORT_METHOD,
        INVALID_SYNTAX_METHOD,
        PRIVATE_METHOD
    ]
    filter_instance = MethodFilter(methods)
    filtered = filter_instance.method_filtering()
    # Should only keep valid instance methods that meet all criteria
    valid_names = {m['name'] for m in filtered}
    expected_names = {'process_data'}  # Only regular instance methods should pass
    assert valid_names == expected_names

def test_is_method_in_class():
    """Test the _is_method_in_class helper function."""
    filter_instance = MethodFilter([])
    assert filter_instance._is_method_in_class(
        VALID_METHOD['context'],
        VALID_METHOD['name']
    ) == True
    assert filter_instance._is_method_in_class(
        NO_CLASS_CONTEXT_METHOD['context'],
        NO_CLASS_CONTEXT_METHOD['name']
    ) == False

def test_get_method_node():
    """Test the _get_method_node helper function."""
    filter_instance = MethodFilter([])
    # Test valid method parsing
    node = filter_instance._get_method_node(VALID_METHOD['code'])
    assert isinstance(node, ast.FunctionDef)
    assert node.name == 'process_data'
    
    # Test invalid syntax
    invalid_node = filter_instance._get_method_node(INVALID_SYNTAX_METHOD['code'])
    assert invalid_node is None

def test_empty_method_list():
    """Test handling of empty method list."""
    filter_instance = MethodFilter([])
    filtered = filter_instance.method_filtering()
    assert len(filtered) == 0
    assert isinstance(filtered, list)
