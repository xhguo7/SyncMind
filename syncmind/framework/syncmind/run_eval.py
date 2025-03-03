import os
import json
import argparse
from typing import Dict, List, Any, Optional
from datetime import datetime

from openhands.core.logger import openhands_logger as logger

class RecoveryEval:
    """
    A class for evaluating LLM task completion with customizable metrics.
    
    This class provides basic functionality to:
    1. Read evaluation data from JSON files
    2. Save evaluation results to JSON files
    3. Support for adding custom metrics (to be implemented by user)
    """
    
    def __init__(self, data_path: str, save_path: str = None):
        """
        Initialize the RecoveryEval class.
        
        Args:
            data_dir: Directory containing input evaluation data
            results_dir: Directory to save evaluation results
        """
        self.data_path = data_path
        self.save_path = save_path
        self.eval_data = self.load_evaluation_data()
        self.total_count = None
        self.eval_result = None

    def _get_output_path(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eval_summary_{timestamp}.json"
        output_dir_path = os.path.dirname(self.data_path)
        self.save_path = os.path.join(output_dir_path, filename)

    def _init_eval_result(self):
        self.total_count = {'total': 0, 'independent': 0, 'collaborative': 0}
        self.eval_result = {
            'total': {
                'SR': {'num': 0, 'rate': 0.0},
                'LA_file': {'num': 0, 'rate': 0.0},
                'LA_func': {'num': 0, 'rate': 0.0},
            },
            'independent': {
                'SR': {'num': 0, 'rate': 0.0},
                'LA_file': {'num': 0, 'rate': 0.0},
                'LA_func': {'num': 0, 'rate': 0.0},
            },
            'collaborative': {
                'SR': {'num': 0, 'rate': 0.0},
                'LA_file': {'num': 0, 'rate': 0.0},
                'LA_func': {'num': 0, 'rate': 0.0},
            },
        }
    
    def read_json(self, file_pth: str) -> Dict[str, Any]:
        """
        Read data from a JSON file.
        
        Args:
            file_pth: Path of the JSON file to read
            
        Returns:
            Dictionary containing the JSON data
            
        Raises:
            FileNotFoundError: If the specified file does not exist
            json.JSONDecodeError: If the file contains invalid JSON
        """
        filepath = os.path.join(file_pth)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            raise FileNotFoundError(f"File not found: {filepath}")
        except json.JSONDecodeError:
            raise json.JSONDecodeError(f"Invalid JSON in file: {filepath}", "", 0)
    
    def load_evaluation_data(self) -> None:
        """
        Load evaluation data from a JSON file and store it in the instance.
        """
        self.eval_data = self.read_json(self.data_path)
        logger.info(f"Loaded evaluation data from `{self.data_path}` with {len(self.eval_data)} entries")
    
    def save_json(self, data: Dict[str, Any], pretty: bool = True) -> None:
        """
        Save data to a JSON file.
        
        Args:
            data: Dictionary data to save
            pretty: Whether to format the JSON with indentation
            
        Raises:
            IOError: If there's an error writing to the file
        """
        try:
            with open(self.save_path, 'w', encoding='utf-8') as f:
                if pretty:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    json.dump(data, f, ensure_ascii=False)
            logger.info(f"Saved data to {self.save_path}")
        except IOError as e:
            raise IOError(f"Error writing to file {self.save_path}: {str(e)}")
    
    def save_results(self) -> None:
        """Save evaluation results to a JSON file."""
        if self.save_path is None:
            self._get_output_path()
        
        # Add metadata to results
        print(f"self.eval_result: {self.eval_result}")
        self.eval_result["metadata"] = {
            "timestamp": str(datetime.now().isoformat()),
            "data_size": len(self.eval_data) if self.eval_data else 0
        }
        
        self.save_json(self.eval_result, self.save_path)
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """
        Evaluation metrics.
        
        Returns:
            Dictionary of calculated metrics
        """
        self._init_eval_result()
        LA_func_i, LA_file_i = 0, 0

        for instance_id in self.eval_data:
            curr_data = self.eval_data[instance_id]['final_instance_eval_result']
            if isinstance(curr_data, Dict):
                curr_recovery_method = self.eval_data[instance_id]['instance_info']['resync_method']
                self.total_count['total'] += 1
                self.total_count[curr_recovery_method] += 1

                if curr_data['adapt']['adapt_grade'] == 1:
                    LA_func_i = 1
                    LA_file_i = 1
                else: 
                    LA_func_i = curr_data['react']['react_grade']
                    LA_file_i = LA_func_i
                    if self.eval_data[instance_id]['instance_info']['pyfile_path'].split('test_repo/')[-1] in curr_data['react']['agent_answer']:
                        LA_file_i = 1
                
                self.eval_result['total']['SR']['num'] += curr_data['adapt']['adapt_grade']
                self.eval_result['total']['LA_func']['num'] += LA_func_i
                self.eval_result['total']['LA_file']['num'] += LA_file_i

                self.eval_result[curr_recovery_method]['SR']['num'] += curr_data['adapt']['adapt_grade']
                self.eval_result[curr_recovery_method]['LA_func']['num'] += curr_data['react']['react_grade']
                self.eval_result[curr_recovery_method]['LA_file']['num'] += LA_file_i

                logger.info(
                    f"\nInstance ID: {instance_id}\n[Recoverry Method] {curr_recovery_method}"
                    f"\n[Eval Result] SR_i = {curr_data['adapt']['adapt_grade']}"
                    f"\n[Eval Result] LA_file_i = {LA_file_i}"
                    f"\n[Eval Result] LA_func_i = {curr_data['react']['react_grade']}"
                )
            else:
                logger.info(f"[WARINING] Skipping the test result of instance due to incomplete testing: instance id = {instance_id}")

        for kk in self.eval_result.keys():
            if self.total_count[kk] > 0:
                self.eval_result[kk]['SR']['rate'] = round(self.eval_result[kk]['SR']['num'] / self.total_count[kk] * 100, 3)
            if self.total_count[kk] > 0:
                self.eval_result[kk]['LA_file']['rate'] = round(self.eval_result[kk]['LA_file']['num'] / self.total_count[kk] * 100, 3)
            if self.total_count[kk] > 0:
                self.eval_result[kk]['LA_func']['rate'] = round(self.eval_result[kk]['LA_func']['num'] / self.total_count[kk] * 100, 3)

        self.save_results()
    
    def run_evaluation(self) -> Dict[str, Any]:
        """
        Run the full evaluation process.
        
        Args:
            input_file: JSON file containing evaluation data
            output_file: Optional custom filename for results
            
        Returns:
            Dictionary of evaluation results
        """
        # Load data
        self.load_evaluation_data()
        
        # Calculate metrics (to be implemented by user)
        self.eval_result = self.calculate_metrics()
        
        return self.eval_result


# Run eval
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--eval_path', type=str, default=None, help='Please enter your eval data path.')
    args = parser.parse_args()

    eval_path = args.eval_path
    evaluator = RecoveryEval(eval_path)

    # Test data path validity
    try:
        data = evaluator.read_json(eval_path)
        logger.info(f"Successfully read {len(data)} items")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error: {str(e)}")
    
    # Run evaluation
    results = evaluator.run_evaluation()
    logger.info("Evaluation complete")
    