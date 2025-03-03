"""
Final evaluation
"""

from typing import Any

import pandas as pd

from evaluation.utils.shared import assert_and_raise
from openhands.core.logger import openhands_logger as logger
from openhands.events.action import CmdRunAction
from openhands.events.observation import CmdOutputObservation
from openhands.runtime.base import Runtime
from evaluation.benchmarks.syncmind.builds.instance import InstanceProcessor
from evaluation.benchmarks.syncmind.builds.extractor import extract_function_code


def complete_runtime(
    runtime: Runtime,
    instance: pd.Series,
    workspace_dir: str
) -> dict[str, Any]:
    """Complete the runtime for the agent.

    This function is called before the runtime is used to run the agent.
    If you need to do something in the sandbox to get the correctness metric after
    the agent has run, modify this function.
    """
    logger.info('-' * 50)
    logger.info('BEGIN Runtime Completion Fn')
    logger.info('-' * 50)
    obs: CmdOutputObservation

    action = CmdRunAction(command=f'cd {workspace_dir}')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0,
        f'Failed to cd to {workspace_dir}: {obs.content}',
    )
    
    inst_processor = InstanceProcessor(instance)
    _, _, target_image_path = inst_processor.instance_restoration()
    action = CmdRunAction(command=f'cat {target_image_path}')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    if not (obs.exit_code == 0):
        logger.info(f"Failed to read file content: {obs.content}")
        file_content, code_content = None, None
    else:
        file_content = obs.content.strip().split('[Python Interpreter')[0].split('(test_venv)')[0]
        code_content = extract_function_code(file_content, instance.fm_name)

    logger.info('-' * 50)
    logger.info('END Runtime Completion Fn')
    logger.info('-' * 50)
    
    return {'updated_code': file_content, 'updated_fm': code_content}
    