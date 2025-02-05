"""
Test Caller
"""

import pytest
from unittest.mock import Mock, patch, mock_open
import json
from pathlib import Path

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from syncbench.constructor.caller import CallerDataConstructor

class TestCallerDataConstructor:
    @pytest.fixture
    def mock_args(self):
        args = Mock()
        args.repo_source_dict_list = [
            {'repo_id': 1, 'name': 'repo1'},
            {'repo_id': 2, 'name': 'repo2'}
        ]
        args.root_path = '/root/'
        args.dataset_path = 'datasets/'
        args.construct_start = 0
        args.construct_end = 2
        return args

    @pytest.fixture
    def constructor(self, mock_args):
        constructor = CallerDataConstructor(mock_args)
        constructor.repo_id = 1
        constructor.repo_name = 'test_repo'
        return constructor

    def test_initialization(self, constructor, mock_args):
        """Test if CallerDataConstructor initializes correctly"""
        assert constructor.data_len == len(mock_args.repo_source_dict_list)
        assert constructor.all_fm_list == []
        assert constructor.dataset_save_path == '/root/datasets/'

    def test_save_to_json(self, constructor):
        """Test if save_to_json writes data correctly"""
        test_data = {'key': 'value'}
        
        with patch('builtins.open', mock_open()) as mock_file:
            constructor.save_to_json(test_data, 'test_path.json')
            
            # Verify file was opened correctly
            mock_file.assert_called_once_with('test_path.json', 'w')
            
            # Get the mock file handle
            handle = mock_file()
            
            # Combine all written content
            written_content = ''.join(call.args[0] for call in handle.write.call_args_list)
            
            # Verify the combined content is valid JSON and matches our data
            assert json.loads(written_content) == test_data

    @patch('syncbench.constructor.caller.EnvConfig')
    @patch('syncbench.constructor.caller.CallerConstructor')
    def test_all_data_construction(self, MockCallerConstructor, MockEnvConfig, constructor, mock_args):
        """Test if all_data_construction processes all repos correctly"""
        mock_env_config = MockEnvConfig.return_value
        mock_benchmark = MockCallerConstructor.return_value
        mock_benchmark.extract_fm_from_in_test_object.return_value = [
            {'function': 'test1'},
            {'function': 'test2'}
        ]

        constructor.all_data_construction(mock_args)

        assert mock_env_config.dataset_construction_config.call_count == 2
        assert MockCallerConstructor.call_count == 2
        assert mock_benchmark.extract_fm_from_in_test_object.call_count == 2
        assert len(constructor.all_fm_list) == 4

    @patch('syncbench.constructor.caller.EnvConfig')
    @patch('syncbench.constructor.caller.CallerConstructor')
    def test_single_repo_data_construction(self, MockCallerConstructor, MockEnvConfig, constructor):
        """Test if single_repo_data_construction processes a repo correctly"""
        mock_env_config = MockEnvConfig.return_value
        mock_benchmark = MockCallerConstructor.return_value
        test_data = [{'function': 'test1'}, {'function': 'test2'}]
        mock_benchmark.extract_fm_from_in_test_object.return_value = test_data

        # Create mock args
        mock_args = Mock()
        
        with patch.object(constructor, 'save_to_json') as mock_save:
            result = constructor.single_repo_data_construction(mock_args, 1)

            mock_env_config.dataset_construction_config.assert_called_once()
            MockCallerConstructor.assert_called_once()
            mock_benchmark.extract_fm_from_in_test_object.assert_called_once()
            
            # Verify save_to_json was called with correct parameters
            expected_save_path = f"{constructor.dataset_save_path}caller_{constructor.repo_id}_{constructor.repo_name}.json"
            mock_save.assert_called_once_with(test_data, expected_save_path)
            assert result == test_data
            