"""
Response generation
"""

import ast
import pandas as pd
from typing import Tuple
from openhands.controller.state.state import State
from openhands.core.message import Message, TextContent
from openhands.core.logger import openhands_logger as logger
from openhands.runtime.base import Runtime
from evaluation.utils.shared import EvalMetadata
from evaluation.benchmarks.syncmind.runs.runtime_eval import extract_agent_revised_code
from evaluation.benchmarks.syncmind.evals.adapt_eval import DockerEvaluator
from evaluation.benchmarks.syncmind.evals.react_eval import ReactEvaluator
from evaluation.benchmarks.syncmind.prompter.user_response import check_progress, codeact_user_response_resync
from evaluation.benchmarks.syncmind.builds.json_util import save_to_json, read_json_data
from evaluation.benchmarks.syncmind.runs.runtime_eval import get_last_action, get_action_message
from evaluation.benchmarks.syncmind.prompter.know_agent import KnowPrompter
from evaluation.benchmarks.syncmind.prompter.interact import openai_api_qa_interaction



# Save intermediate result to dict
def save_progress_to_dict(
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

    # Save test_result for current instance
    test_result_dict_save_path = metadata.details['output_save_path'] + f'test_result_dict_instance_{instance.instance_id}.json'
    # Init test_result_dict for current instance
    test_result_dict = read_json_data(test_result_dict_save_path)
    # Cost-aware out-of-sync recovery
    if instance.instance_id not in test_result_dict.keys():
        test_result_dict[instance.instance_id] = {
            'instance_eval_result': {}, 
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
                # 'old_filtered_context': instance.old_filtered_context, 
                # 'new_complete_context': instance.new_complete_context, 
                'initial_error_log': instance.initial_error_log, 
                'pyfile_path': instance.pyfile_path, 
                'unittest_path': instance.unittest_path, 
                'resync_method': metadata.details['resync_method'], 
                'total_budget': metadata.details['total_budget'], 
                'coding_cost': metadata.details['coding_cost'], 
                'asking_cost': metadata.details['asking_cost']
            },
        }
    # Save to test_result_dict
    if f"turn {state.local_iteration}" not in test_result_dict[instance.instance_id].keys():
        test_result_dict[instance.instance_id][f"turn {state.local_iteration}"] = {'agent_message': message_content, 'agent_updated_code': test_result['updated_fm'], 'human_response': fake_user_response, 'current_balance': test_result['current_balance'], 'current_turn_instance_eval_result': instance_result}
    # Save interaction history to test_result_dict
    test_result_dict[instance.instance_id]['interaction_history'] += interaction_update
    # Save overall instance eval result
    if f"turn {state.local_iteration}" not in test_result_dict[instance.instance_id]['instance_eval_result'].keys():
        test_result_dict[instance.instance_id]['instance_eval_result'][f'turn {state.local_iteration}'] = instance_result
    # Save to file
    save_to_json(test_result_dict, test_result_dict_save_path)
    
    # Save to all_test_result
    all_test_result_dict_path = metadata.details['output_save_path'] + 'all_test_result_dict.json'
    all_test_result_dict = read_json_data(all_test_result_dict_path)
    all_test_result_dict[instance.instance_id] = test_result_dict[instance.instance_id]  # update all eval result for current instance
    save_to_json(all_test_result_dict, all_test_result_dict_path)


def parsing_message_text(
        message: Message
    ) -> str:
    text_contents = []

    for item in message.content:
        if isinstance(item, TextContent):
            text_contents.append(item.text)
    full_text = " ".join(text_contents)
    return full_text


"""
MessageAction: Waiting for User Response
"""
def get_fake_user_response(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> Tuple[str, bool]:

    # Get agent's revised code
    test_result = extract_agent_revised_code(runtime, instance, workspace_dir)
    test_result['resync_method'] = metadata.details['resync_method']
    test_result['total_budget'] = metadata.details['total_budget']
    test_result['coding_cost'] = metadata.details['coding_cost']
    test_result['asking_cost'] = metadata.details['asking_cost']
    logger.info(f"Agent updated code for instance {instance.instance_id}:\n--------\n{test_result['updated_fm']}\n--------")
    
    # Process message
    last_action = get_last_action(state)
    message_content = last_action.message

    # Base message
    encaps_str = (
        'Please encapsulate your final answer (answer ONLY) within <solution> and </solution>.\n'
        'For example: The answer to the question is <solution> def func(): ... </solution>.\n'
    )
    base_msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'If you think you have solved the task, please send your answer to user through message.\n'
        'You CANNOT finish the interaction unless the user confirm the correctness of your solution.'
        f'{encaps_str}'
    )
    
    '''
    Collaborative: Question asking
    '''
    if (metadata.details['resync_method'] == 'collaborative') and ("[QUESTION]" in message_content):
        test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
        current_balance = state.extra_data['current_balance'] - metadata.details['asking_cost']
        know_answerer = KnowPrompter(instance, metadata)
        know_answer_prompt = know_answerer.know_everything_answerer(message_content.replace('<question>', '').replace('</question>', '').strip())
        know_answer = openai_api_qa_interaction(metadata.llm_config, know_answer_prompt)
        fake_user_response = f"{base_msg}\n[Balance: ${current_balance} Left] {know_answer}"
        interaction_update = f"{last_action.source.upper()} [MessageAction]:\n{message_content}\n\n" + f"USER:\n{fake_user_response}\n\n"
        test_result['current_balance'] = current_balance
        save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, message_content, fake_user_response)
        return fake_user_response, current_balance, 'asking'

    '''
    Error cause explanation + revision plan + code revision
    '''
    # React eval
    if message_content == "":
        react_eval_grade = 0
        react_eval_result = {
            'agent_answer': message_content, 
            'react_grade': react_eval_grade
        }
    else:
        react_evaluator = ReactEvaluator(instance, message_content)
        react_eval_grade = react_evaluator.agent_message_react_eval()
        react_eval_result = {
            'agent_answer': message_content, 
            'react_grade': react_eval_grade
        }
    
    # Update balance
    current_balance = state.extra_data['current_balance']
    current_balance -= metadata.details['coding_cost']
    test_result['current_balance'] = current_balance

    # Adapt eval: code revision evaluation via unit test
    evalor = DockerEvaluator(instance, test_result)
    unittest_result = evalor.run_unittest()

    # Update faked user response
    fake_user_response = codeact_user_response_resync(state, instance, test_result, unittest_result)

    # Update interaction history
    interaction_update = f"{last_action.source.upper()} [MessageAction]:\n{message_content}\n\n" + f"USER:\n{fake_user_response}\n\n"
    
    # Save unittest_result to test_result
    test_result['adapt_grade'] = unittest_result['adapt_grade']
    test_result['adapt_comment'] = unittest_result['adapt_comment']
    
    # Check resync progress
    current_progress = check_progress(instance, test_result)
    if (state.local_iteration + 1) == state.max_iterations:
        if test_result['adapt_grade'] == 1:
            current_progress = 'success'
        else:
            current_progress = 'failed'
    # Save to instance_result
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
            'reason': 'failed unit test at current turn', 
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

    instance_result = {
        'current_turn': state.local_iteration,
        'react': react_eval_result,
        'adapt': adapt_eval_result
    }
    
    # Save result
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, instance_result, test_result, message_content, fake_user_response)
    
    return fake_user_response, current_balance, 'coding'
    

"""
IPythonRunCellAction
"""
def save_current_turn_ipythonaction(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> None:
    last_event = state.history[-1]
    ipython_code = last_event.code
    agent_thought = last_event.message

    '''
    Env interaction
    '''
    current_balance = state.extra_data['current_balance']  # balance unchanged
    interaction_update = f"{last_event.source.upper()} [IPythonRunCellAction]:\n[IPythonCode]\n{ipython_code}\n[Agent Message]\n{agent_thought}\n\n"

    # Get agent's revised code
    test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
    test_result['current_balance'] = current_balance
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, interaction_update, None)
    
"""
CmdRunAction
"""
def save_current_turn_cmdaction(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> None:
    last_event = state.history[-1]
    command = last_event.command
    agent_thought = last_event.message

    '''
    Env interaction
    '''
    current_balance = state.extra_data['current_balance']  # balance unchanged
    interaction_update = f"{last_event.source.upper()} [CmdRunAction]:\n[Command]\n{command}\n[Agent Message]\n{agent_thought}\n\n"

    # Get agent's revised code
    test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
    test_result['current_balance'] = current_balance
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, interaction_update, None)


"""
AgentFinishAction
"""
def save_current_turn_finishaction(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> None:
    last_event = state.history[-1]
    agent_thought = last_event.message

    '''
    Agent Finish Action
    '''
    current_balance = state.extra_data['current_balance']  # balance unchanged
    interaction_update = f"{last_event.source.upper()} [{type(last_event)}]:\n[Agent Message]\n{agent_thought}\n\n" + f"---------- INTERACTION END ----------\n[Final Balance: ${current_balance}] Task Completed for Instance with ID `{instance.instance_id}`\n\n"

    # Get agent's revised code
    test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
    test_result['current_balance'] = current_balance
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, interaction_update, None)


"""
Other Action
"""
    
def save_current_turn_othermessageaction(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> str:
    last_event = state.history[-1]
    agent_thought = last_event.message

    '''
    Message Action
    '''
    current_balance = state.extra_data['current_balance']  # balance unchanged
    user_response = f"""[Balance: {current_balance} Left] You may try to provide your textual answer consists of both the absolute path of your revised Python file and the name of your revised function/method according to the required format after revising `test_repo`. You CANNOT finish this task until the USER confirm that your revised `test_repo` have passed USER's evaluation."""
    interaction_update = f"{last_event.source.upper()} [{type(last_event)}]:\n[Agent Message]\n{agent_thought}\n\nUSER:\n{user_response}\n"
    
    # Get agent's revised code
    test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
    test_result['current_balance'] = current_balance
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, interaction_update, None)
    
    return user_response

def save_current_turn_otheraction(
        state: State,
        runtime: Runtime,
        instruction: str,
        instance: pd.Series, 
        workspace_dir: str, 
        metadata: EvalMetadata
    ) -> str:
    last_event = state.history[-1]
    agent_thought = last_event.message

    # Base message
    encaps_str = (
        'Please encapsulate your final answer (answer ONLY) within <solution> and </solution>.\n'
        'For example: The answer to the question is <solution> def func(): ... </solution>.\n'
    )
    base_msg = (
        'Please continue working on the task on whatever approach you think is suitable.\n'
        'If you think you have solved the task, please send your answer to user through message.\n'
        'You CANNOT finish the interaction unless the user confirm the correctness of your solution.'
        f'{encaps_str}'
    )

    '''
    Env interaction
    '''
    current_balance = state.extra_data['current_balance']  # balance unchanged
    user_response = f"""{base_msg}\n[Balance: {current_balance} Left] You may try to provide your textual answer consists of both the absolute path of your revised Python file and the name of your revised function/method according to the required format after revising `test_repo`. You CANNOT finish this task until the USER confirm that your revised `test_repo` have passed USER's evaluation."""
    interaction_update = f"{last_event.source.upper()} [{type(last_event)}]:\n[Agent Message]\n{agent_thought}\n\n" + f"USER:\n{user_response}\n\n"

    # Get agent's revised code
    test_result = {'updated_code': None, 'updated_fm': None, 'resync_method': metadata.details['resync_method']}
    test_result['current_balance'] = current_balance
    save_progress_to_dict(state, instance, metadata, instruction, interaction_update, None, test_result, interaction_update, None)
    
    return user_response

    