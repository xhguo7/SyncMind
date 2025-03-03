"""
Evaluate agent's code revision in a runtime
"""

import pandas as pd
from typing import Any, Optional
from openhands.events.action import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)
from openhands.events.observation import CmdOutputObservation
from openhands.controller.state.state import State
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import ImageContent, Message, TextContent
from openhands.runtime.base import Runtime
from evaluation.benchmarks.syncbench.builds.instance import InstanceProcessor
from evaluation.benchmarks.syncbench.builds.extractor import extract_function_code


def get_last_action(state: State) -> Optional[Action]:
    last_action = None
    if state.history:
        last_action = next(
            (
                event
                for event in reversed(state.history)
                if isinstance(event, Action)
            ),
            None,
        )
    return last_action

def get_last_action_message(state: State) -> str:
    if state.history:
        last_action = next(
            (
                event
                for event in reversed(state.history)
                if isinstance(event, Action)
            ),
            None,
        )
        ans = last_action.message
    return ans

# Convert action to str
def action_to_str(action: Action) -> str:
    if isinstance(action, CmdRunAction):
        return (
            f'{action.thought}\n<execute_bash>\n{action.command}\n</execute_bash>'
        )
    elif isinstance(action, IPythonRunCellAction):
        return f'{action.thought}\n<execute_ipython>\n{action.code}\n</execute_ipython>'
    elif isinstance(action, AgentDelegateAction):
        return f'{action.thought}\n<execute_browse>\n{action.inputs["task"]}\n</execute_browse>'
    elif isinstance(action, MessageAction):
        return action.content
    elif isinstance(action, AgentFinishAction) and action.source == 'agent':
        return action.thought
    return ''

    
def get_action_message(action: Action) -> Message | None:
    """Get action message"""
    if (
        isinstance(action, AgentDelegateAction)
        or isinstance(action, CmdRunAction)
        or isinstance(action, IPythonRunCellAction)
        or isinstance(action, MessageAction)
        or (isinstance(action, AgentFinishAction) and action.source == 'agent')
    ):
        content = [TextContent(text=action_to_str(action))]

        if isinstance(action, MessageAction) and action.images_urls:
            content.append(ImageContent(image_urls=action.images_urls))

        return Message(
            role='user' if action.source == 'user' else 'assistant', content=content
        )
    return None


def extract_agent_revised_code(
        runtime: Runtime,
        instance: pd.Series, 
        workspace_dir: str
    ) -> dict[str, Any]:
    """ [Adapt Eval] Prepare: Extract agent's code revision
    Extract agent's revised code
    """
    logger.info('-' * 50)
    logger.info('BEGIN Agent Code Generation Extraction')
    logger.info('-' * 50)
    obs: CmdOutputObservation

    action = CmdRunAction(command=f'cd {workspace_dir}')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})

    # Process instance info
    inst_processor = InstanceProcessor(instance)
    _, _, target_image_path = inst_processor.instance_restoration()
    
    # Read the content of the target file
    action = CmdRunAction(command=f'cat {target_image_path}')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    file_content = obs.content.strip().split('[Python Interpreter')[0].split('(test_venv)')[0]
    code_content = extract_function_code(file_content, instance.fm_name)

    logger.info('-' * 50)
    logger.info('END Agent Code Generation Extraction')
    logger.info('-' * 50)
    
    return {'updated_code': file_content, 'updated_fm': code_content}



