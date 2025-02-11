"""
Final eval to complete runtime
"""

import os
import sys
import ast
import asyncio
import hashlib
import copy
import pandas as pd
from typing import Callable, Protocol, Type, Tuple

from openhands.events.action import MessageAction
from openhands.controller.state.state import State
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import Message
from openhands.runtime.runtime import Runtime
from evaluation.utils.shared import EvalMetadata
from evaluation.syncmind.evals.adapt_eval import DockerEvaluator
from evaluation.syncmind.evals.react_eval import ReactEvaluator
from evaluation.syncmind.runs.runtime_eval import get_action_message
from evaluation.syncmind.prompter.user_response import check_progress, codeact_user_response_resync
from evaluation.syncmind.builds.json_util import save_to_json, read_json_data
from evaluation.syncmind.runs.runtime_response import parsing_message_text


def get_last_react_eval(
        state: State, 
        instance: pd.Series, 
        metadata: EvalMetadata,
    ) -> dict:  # return dict or None
    """Get the last react eval if exists"""
    test_result_dict_save_path = metadata.details['output_save_path'] + f'test_result_dict_instance_{instance.instance_id}.json'
    test_result_dict = read_json_data(test_result_dict_save_path)
    if f'turn {state.local_iteration}' not in test_result_dict[instance.instance_id]['instance_eval_result'].keys():
        state.local_iteration = state.local_iteration - 1
    last_turn_instance_result = test_result_dict[instance.instance_id]['instance_eval_result'][f'turn {state.local_iteration}']
    if last_turn_instance_result != None:
        return last_turn_instance_result['react']
    return None


def search_correct_react_answer(
        state: State, 
        instance: pd.Series, 
        metadata: EvalMetadata,
    ) -> Tuple[dict, int]:
    """Search for the correct react answer if exists"""
    test_result_dict_save_path = metadata.details['output_save_path'] + f'test_result_dict_instance_{instance.instance_id}.json'
    test_result_dict = read_json_data(test_result_dict_save_path)
    if test_result_dict[instance.instance_id]['instance_eval_result'] == {}:
        return None, None
    
    # Search for correct react answer
    # for turn_idx in range(state.local_iteration, 0, -1):  # reversed order: search for the last correct react answer
    for turn_idx in range(1, state.local_iteration+1):  # normal order: search for the first correct react answer
        current_turn_instance_result = test_result_dict[instance.instance_id]['instance_eval_result'][f'turn {turn_idx}']
        # If current turn is empty: agent didn't provide answer at this turn
        if not current_turn_instance_result:
            continue
        if current_turn_instance_result['react']['react_grade'] == 1:
            return current_turn_instance_result, turn_idx
    return None, None


def save_final_eval_to_dict(
        state: State, 
        instance: pd.Series, 
        metadata: EvalMetadata,
        instruction: str,
        interaction_update: str,
        instance_result: dict,
        test_result: dict, 
        message_content: Message, 
        fake_user_response: str
    ) -> None:
    """Save final eval result"""

    test_result_dict_save_path = metadata.details['output_save_path'] + f'test_result_dict_instance_{instance.instance_id}.json'
    test_result_dict = read_json_data(test_result_dict_save_path)
    if instance.instance_id not in test_result_dict.keys():
        test_result_dict[instance.instance_id] = {
            'instance_eval_result': '[Abnormal Case] No previous turns', 
            'final_instance_eval_result': 'TBD: Final evaluation will be performed in completing runtime...', 
            'interaction_history': instruction,
            'instance_info': {
                'instance_id': instance.instance_id,
                'repo_url': instance.repo_url,
                'commit': instance.commit, 
                'fm_type': instance.fm_type, 
                'fm_name': instance.fm_name, 
                'pyfile_name': instance.pyfile_name, 
                'original_code': instance.original_code,
                'gold_code': instance.gold_code, 
                'initial_error_log': instance.initial_error_log, 
                'pyfile_path': instance.pyfile_path, 
                'unittest_path': instance.unittest_path, 
                'resync_method': metadata.details['resync_method'], 
                'total_budget': metadata.details['total_budget'], 
                'coding_cost': metadata.details['coding_cost'], 
                'asking_cost': metadata.details['asking_cost']
            },
        }
    
    test_result_dict[instance.instance_id][f"[FINAL] turn {state.local_iteration}"] = {'agent_answer': message_content, 'agent_updated_code': test_result['updated_fm'], 'human_response': fake_user_response, 'current_balance': test_result['current_balance'], 'current_turn_instance_eval_result': instance_result}
    test_result_dict[instance.instance_id]['interaction_history'] += interaction_update
    test_result_dict[instance.instance_id]['final_instance_eval_result'] = instance_result
    save_to_json(test_result_dict, test_result_dict_save_path)
    all_test_result_dict_path = metadata.details['output_save_path'] + 'all_test_result_dict.json'
    all_test_result_dict = read_json_data(all_test_result_dict_path)
    all_test_result_dict[instance.instance_id] = test_result_dict[instance.instance_id]
    save_to_json(all_test_result_dict, all_test_result_dict_path)
    return test_result_dict


def complete_runtime_eval(
    state: State,
    runtime: Runtime,
    instruction: str,
    instance: pd.Series, 
    workspace_dir: str, 
    metadata: EvalMetadata, 
    basic_test_result: dict
) -> Tuple[dict, bool]:
    """Complete runtime"""

    test_result = copy.deepcopy(basic_test_result)
    test_result['resync_method'] = metadata.details['resync_method']
    test_result['total_budget'] = metadata.details['total_budget']
    test_result['coding_cost'] = metadata.details['coding_cost']
    test_result['asking_cost'] = metadata.details['asking_cost']
    logger.info(f"Runtime completing for instance {instance.instance_id}...")
    
    last_action = state.history.get_last_action()
    action_message = get_action_message(last_action)
    if last_action.source == 'agent':
        message_content = parsing_message_text(action_message)
    else:
        message_content = state.history.get_last_agent_message() + '\n' + parsing_message_text(action_message)

    react_eval_grade = 0
    react_eval_result = get_last_react_eval(state, instance, metadata)
    if not react_eval_result:
        react_evaluator = ReactEvaluator(instance, message_content)
        react_eval_grade = react_evaluator.agent_message_react_eval()
        react_eval_result = {
            'current_turn': f'turn {state.local_iteration}',
            'agent_answer': message_content, 
            'react_grade': react_eval_grade
        }
    else:
        react_eval_grade = react_eval_result['react_grade']

    # Search for the first correct react answer if exists
    if react_eval_grade != 1:
        instance_result_with_correct_react, turn_idx = search_correct_react_answer(state, instance, metadata)
        if instance_result_with_correct_react:
            react_eval_result = {
                'current_turn': f'turn {turn_idx}',
                'agent_answer': instance_result_with_correct_react['react']['agent_answer'], 
                'react_grade': instance_result_with_correct_react['react']['react_grade']
            }
    
    # Get current balance
    current_balance = state.extra_data['current_balance']
    test_result['current_balance'] = current_balance
    
    # Adapt eval: code revision evaluation via unit test
    evalor = DockerEvaluator(instance, test_result)
    unittest_result = evalor.run_unittest()

    # Update user response
    fake_user_response = codeact_user_response_resync(state, instance, test_result, unittest_result)
    fake_user_response = fake_user_response.replace("Please try again.", "")
    interaction_update = f"{last_action.source.upper()}:\n{message_content}\n\n" + f"USER:\n{fake_user_response}\n\n"

    # Save unittest_result to test_result
    test_result['adapt_grade'] = unittest_result['adapt_grade']
    test_result['adapt_comment'] = unittest_result['adapt_comment']

    # Check progress
    current_progress = check_progress(instance, test_result)
    if state.local_iteration == state.max_iterations:
        if test_result['adapt_grade'] == 1:
            current_progress = 'success'
        else:
            current_progress = 'failed'
    
    if current_progress == 'out-of-balance':
        adapt_eval_result = {
            'adapt_grade': unittest_result['adapt_grade'], 
            'adapt_comment': unittest_result['adapt_comment'], 
            'reason': 'success' if int(unittest_result['adapt_grade']) == 1 else 'running out-of-balance without passing unit test', 
            'summary': unittest_result['summary']
        }
    elif current_progress == 'failed':
        adapt_eval_result = {
            'adapt_grade': unittest_result['adapt_grade'], 
            'adapt_comment': unittest_result['adapt_comment'], 
            'reason': 'reached max-turn limit without passing unit test', 
            'summary': unittest_result['summary']
        }
    elif current_progress == 'success':
        adapt_eval_result = {
            'adapt_grade': unittest_result['adapt_grade'], 
            'adapt_comment': unittest_result['adapt_comment'], 
            'reason': 'success', 
            'summary': unittest_result['summary']
        }
    else:  # continue
        adapt_eval_result = {
            'adapt_grade': unittest_result['adapt_grade'], 
            'adapt_comment': unittest_result['adapt_comment'], 
            'reason': 'failed unit test', 
            'summary': unittest_result['summary']
        }
    
    # In case of not submitting answer but reached max-turn limit
    if not isinstance(last_action, MessageAction):
        if state.local_iteration == metadata.max_iterations:
            adapt_eval_result = {
                'adapt_grade': unittest_result['adapt_grade'], 
                'adapt_comment': unittest_result['adapt_comment'], 
                'reason': 'reached max-turn limit without submitting answer', 
                'summary': unittest_result['summary']
            }
    
    # One-by-one parsing alignment between gold_summary and test_summary for "adapt_grade=1" eval result
    if adapt_eval_result['adapt_grade'] == 1:
        count_aligned_key = 0
        for eval_key in unittest_result['summary'].keys():
            if unittest_result['summary'][eval_key] == ast.literal_eval(instance.gold_summary)[eval_key]:
                count_aligned_key += 1
        if count_aligned_key != len(unittest_result['summary'].keys()):
            adapt_eval_result['adapt_grade'] = 0
            adapt_eval_result['reason'] = 'failed unit test at current turn'
            
    # Save gold_summary for checking
    adapt_eval_result['gold_summary'] = ast.literal_eval(instance.gold_summary)

    instance_result = {
        'final_turn': state.local_iteration,
        'final_balance': current_balance,
        'coding_turn': state.extra_data['coding_turn'],
        'asking_turn': state.extra_data['asking_turn'],
        'react': react_eval_result,
        'adapt': adapt_eval_result
    }
    
    # Save result
    test_result_dict = save_final_eval_to_dict(state, instance, metadata, instruction, interaction_update, instance_result, test_result, message_content, fake_user_response)
    
    return test_result_dict
