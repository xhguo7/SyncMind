"""
Unit test on SyncBench
"""

import pytest
import pandas as pd
from unittest.mock import patch, MagicMock

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from syncbench.constructor.syncbench import (
    dataset_to_benchset,
    read_csv_to_df,
    save_df_to_csv,
    check_if_saved_before,
    syncbench_construction
)


@pytest.fixture
def sample_dataset():
    return [{
        'repo': {
            'repo_id': '123',
            'repo_name': 'test_repo',
            'repo_url': 'https://github.com/test/test_repo'
        },
        'context_data': {
            'pyfile_name': 'test.py',
            'old_context_code': {
                'filtered_code': 'old_filtered',
                'complete_code': 'old_complete'
            },
            'new_context_code': {
                'filtered_code': 'new_filtered',
                'complete_code': 'new_complete'
            }
        },
        'fm_data': {
            'fm_type': 'function',
            'fm_name': 'test_function',
            'original_code': 'def test(): pass',
            'gold_code': 'def test(): return True'
        },
        'changes': {
            'commit_id': 'abc123',
            'initial_error_log': 'error',
            'original_summary': 'original',
            'gold_summary': 'gold',
            'fm_absolute_path': '/path/to/test_repo/file.py',
            'usage_test_file_path': '/path/to/test_repo/test_file.py'
        }
    }]

@pytest.fixture
def mock_args():
    args = MagicMock()
    args.dataset = 'callee'
    args.root_path = 'test_root'
    args.dataset_path = 'datasets'
    args.syncbench_path = 'syncbench'
    args.construct_source = 'test'
    args.repo_source_dict_list = [{'repo_name': 'test_repo'}]
    return args

def test_dataset_to_benchset(sample_dataset, mock_args):
    """Test dataset_to_benchset function"""
    result_df = dataset_to_benchset(mock_args, sample_dataset)
    
    assert isinstance(result_df, pd.DataFrame)
    assert len(result_df) == 1
    
    # Check if all expected columns are present
    expected_columns = [
        'instance_id', 'instance_type', 'repo_url', 'commit',
        'fm_type', 'fm_name', 'pyfile_name', 'original_code',
        'gold_code', 'old_filtered_context', 'old_complete_context',
        'new_filtered_context', 'new_complete_context', 'initial_error_log',
        'original_summary', 'gold_summary', 'pyfile_path', 'unittest_path'
    ]
    for col in expected_columns:
        assert col in result_df.columns
        
    # Verify instance_id format (using raw strings to avoid any escaping issues)
    expected_id = r"123_test_repo_callee__test__test_function__abc123"
    actual_id = result_df['instance_id'].iloc[0]
    assert actual_id == expected_id, f"Expected '{expected_id}', but got '{actual_id}'"

@patch('os.path.exists')
@patch('os.path.getsize')
@patch('builtins.open', create=True)
@patch('pandas.read_csv')
def test_read_csv_to_df_nonexistent_file(mock_read_csv, mock_open, mock_getsize, mock_exists):
    """Test read_csv_to_df with nonexistent file"""
    mock_exists.return_value = False
    mock_open.return_value = MagicMock()
    
    result = read_csv_to_df('nonexistent.csv')
    assert result is None
    mock_open.assert_called_once()

@patch('os.path.exists')
@patch('os.path.getsize')
@patch('pandas.read_csv')
def test_read_csv_to_df_empty_file(mock_read_csv, mock_getsize, mock_exists):
    """Test read_csv_to_df with empty file"""
    mock_exists.return_value = True
    mock_getsize.return_value = 0
    
    result = read_csv_to_df('empty.csv')
    assert result is None
    mock_read_csv.assert_not_called()

@patch('pandas.DataFrame.to_csv')
def test_save_df_to_csv(mock_to_csv):
    """Test save_df_to_csv function"""
    test_df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
    save_path = 'test.csv'
    
    save_df_to_csv(test_df, save_path)
    mock_to_csv.assert_called_once_with(save_path, index=False, encoding='utf-8')

def test_check_if_saved_before_with_existing_df():
    """Test check_if_saved_before with existing DataFrame"""
    existing_df = pd.DataFrame({
        'instance_id': ['1', '2'],
        'data': ['a', 'b']
    })
    new_df = pd.DataFrame({
        'instance_id': ['3'],
        'data': ['c']
    })
    
    result = check_if_saved_before(existing_df, new_df)
    
    assert len(result) == 3
    assert list(result['instance_id']) == ['1', '2', '3']

def test_check_if_saved_before_with_no_existing_df():
    """Test check_if_saved_before with no existing DataFrame"""
    new_df = pd.DataFrame({
        'instance_id': ['1'],
        'data': ['a']
    })
    
    result = check_if_saved_before(None, new_df)
    
    assert len(result) == 1
    assert result['instance_id'].iloc[0] == '1'

@patch('os.path.exists')
@patch('syncbench.constructor.syncbench.read_test_data')
@patch('syncbench.constructor.syncbench.save_df_to_csv')
@patch('syncbench.constructor.syncbench.read_csv_to_df')
def test_syncbench_construction(mock_read_csv, mock_save_df, mock_read_data, mock_exists, mock_args, sample_dataset):
    """Test syncbench_construction function"""
    # Setup mocks
    mock_exists.return_value = True
    mock_read_data.return_value = sample_dataset
    mock_read_csv.return_value = None  # Simulating no existing CSV
    
    syncbench_construction(mock_args, 0)
    
    # Verify save_df_to_csv was called twice
    assert mock_save_df.call_count == 2
    # Verify read_csv_to_df was called
    assert mock_read_csv.call_count == 1

@patch('os.path.exists')
def test_syncbench_construction_missing_dataset(mock_exists, mock_args):
    """Test syncbench_construction when dataset doesn't exist"""
    mock_exists.return_value = False
    syncbench_construction(mock_args, 0)
    # Should return without error if dataset doesn't exist
