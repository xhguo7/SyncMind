"""
Run controller as in main
"""

import os
import sys
import uuid
import asyncio
import hashlib
import json
import pandas as pd
from typing import Callable, Protocol, Type, Tuple

from openhands.controller import AgentController
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.core.schema import AgentState
from openhands.events.action import (
    AgentDelegateAction,
    AgentFinishAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
)
from openhands.events.action.action import Action
from openhands.events import EventSource, EventStream, EventStreamSubscriber
from openhands.events.event import Event
from openhands.events.observation import AgentStateChangedObservation
from openhands.events.serialization.event import event_to_trajectory
from openhands.llm.llm import LLM
from openhands.runtime import get_runtime_cls
from openhands.runtime.runtime import Runtime
from openhands.storage import get_file_store
from openhands.core.main import generate_sid, create_runtime
from evaluation.utils.shared import EvalMetadata
from evaluation.syncmind.runs.final_eval import complete_runtime
from evaluation.syncmind.runs.runtime_complete import complete_runtime_eval
from evaluation.syncmind.builds.prep import container_init_for_instance
from evaluation.syncmind.runs.runtime_response import (
    get_fake_user_response, 
    save_current_turn_ipythonaction, 
    save_current_turn_cmdaction, 
    save_current_turn_finishaction, 
    save_current_turn_otheraction, 
    save_current_turn_othermessageaction
)


async def run_controller(
        config: AppConfig,
        instruction: str,
        initial_user_action: Action,
        instance: pd.Series, 
        workspace_dir: str,
        metadata: EvalMetadata,
        sid: str | None = None,
        runtime: Runtime | None = None,
        agent: Agent | None = None,
        exit_on_message: bool = False,
        headless_mode: bool = True
    ) -> State | None:
    """Main coroutine to run the agent controller with task input flexibility.
    It's only used when you launch openhands backend directly via cmdline.

    Args:
        config: The app config.
        instruction: Instruction on the task to run. 
        runtime: (optional) A runtime for the agent to run on.
        agent: (optional) A agent to run.
        exit_on_message: quit if agent asks for a message from user (optional)
        fake_user_response_fn: An optional function that receives the current state
            (could be None) and returns a fake user response.
        headless_mode: Whether the agent is run in headless mode.
    """
    # Create the agent
    if agent is None:
        agent_cls: Type[Agent] = Agent.get_cls(config.default_agent)
        agent_config = config.get_agent_config(config.default_agent)
        llm_config = config.get_llm_config_from_agent(config.default_agent)
        agent = agent_cls(
            llm=LLM(config=llm_config),
            config=agent_config,
        )

    # make sure the session id is set
    sid = sid or generate_sid(config)

    if runtime is None:
        runtime = create_runtime(config, sid=sid)
    
    event_stream = runtime.event_stream
    # restore cli session if enabled
    initial_state = None
    if config.enable_cli_session:
        try:
            logger.info(f'Restoring agent state from cli session {event_stream.sid}')
            initial_state = State.restore_from_session(
                event_stream.sid, event_stream.file_store
            )
        except Exception as e:
            logger.info(f'Error restoring state: {e}')

    # Init controller with this initial state
    controller = AgentController(
        agent=agent,
        max_iterations=config.max_iterations,
        max_budget_per_task=config.max_budget_per_task,
        agent_to_llm_config=config.get_agent_to_llm_config_map(),
        event_stream=event_stream,
        initial_state=initial_state,
        headless_mode=headless_mode,
    )

    if controller is not None:
        controller.agent_task = asyncio.create_task(controller.start_step_loop())

    if initial_state == None:
        controller.get_state().extra_data = metadata.details
        controller.get_state().extra_data['current_balance'] = metadata.details['total_credit']
        controller.get_state().extra_data['env_turn'] = 0
        controller.get_state().extra_data['coding_turn'] = 0
        controller.get_state().extra_data['asking_turn'] = 0

    # Env init
    container_init_for_instance(runtime, instance, metadata)

    assert isinstance(
        initial_user_action, Action
    ), f'initial user actions must be an Action, got {type(initial_user_action)}'
    # Logging
    logger.info(
        f'Agent Controller Initialized: Running agent {agent.name}, model '
        f'{agent.llm.config.model}, with actions: {initial_user_action}'
    )
    
    # start event is a MessageAction with the task, either resumed or new
    if config.enable_cli_session and initial_state is not None:
        # we're resuming the previous session
        event_stream.add_event(
            MessageAction(
                content=(
                    "Let's get back on track. If you experienced errors before, do "
                    'NOT resume your task. Ask me about it.'
                ),
            ),
            EventSource.USER,
        )
    elif initial_state is None:
        # init with the provided actions
        event_stream.add_event(initial_user_action, EventSource.USER)

    async def on_event(event: Event):
        if isinstance(event, AgentStateChangedObservation):
            if event.agent_state == AgentState.AWAITING_USER_INPUT:
                if exit_on_message:
                    message = '/exit'
                else:
                    message, current_balance, action_type = get_fake_user_response(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                    controller.get_state().extra_data['current_balance'] = current_balance
                    if action_type == 'coding':
                        controller.get_state().extra_data['coding_turn'] += 1
                    else:  # action_type == 'asking'
                        controller.get_state().extra_data['asking_turn'] += 1
                
                # If exit due to running out of budget
                if ((metadata.details['resync_method'] == 'independent') and (current_balance < metadata.details['coding_cost'])) \
                    or (metadata.details['resync_method'] == 'collaborative') and (current_balance < min(metadata.details['coding_cost'], metadata.details['asking_cost'])):
                    # Save session when we're about to close
                    if config.enable_cli_session:
                        end_state = controller.get_state()
                        end_state.save_to_session(event_stream.sid, event_stream.file_store)

                    # Final evaluation to complete runtime before close
                    test_result = complete_runtime(runtime, instance, workspace_dir)
                    test_result_dict = complete_runtime_eval(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata, test_result)

                    # Close when done
                    await controller.close()
                    state = controller.get_state()
                    return state, test_result_dict
                
                # If still have enough balance
                action = MessageAction(content=message)
                event_stream.add_event(action, EventSource.USER)

        else:
            controller.get_state().extra_data['env_turn'] += 1
            last_action = controller.get_state().history.get_last_action()
            if isinstance(last_action, IPythonRunCellAction):
                save_current_turn_ipythonaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
            elif isinstance(last_action, CmdRunAction):
                save_current_turn_cmdaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
            else:
                if event.source == 'agent':
                    if isinstance(last_action, AgentFinishAction):
                        save_current_turn_finishaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                    elif isinstance(last_action, MessageAction):
                        message = save_current_turn_othermessageaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                    else:
                        message = save_current_turn_otheraction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                        action = MessageAction(content=message)
                        event_stream.add_event(action, EventSource.USER)
    
    event_stream.subscribe(EventStreamSubscriber.MAIN, on_event)
    while controller.state.agent_state not in [
        AgentState.FINISHED,
        AgentState.REJECTED,
        AgentState.ERROR,
        AgentState.PAUSED,
        AgentState.STOPPED,
    ]:
        await asyncio.sleep(1)  # Give back control for a tick, so the agent can run
    
    # Save session when we're about to close
    if config.enable_cli_session:
        end_state = controller.get_state()
        end_state.save_to_session(event_stream.sid, event_stream.file_store)

    # Final evaluation to complete runtime before close
    test_result = complete_runtime(runtime, instance, workspace_dir)
    test_result_dict = complete_runtime_eval(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata, test_result)
    
    # Close when done
    await controller.close()
    state = controller.get_state()
    
    # Save trajectories if applicable
    if config.trajectories_path is not None:
        file_path = os.path.join(config.trajectories_path, sid + '.json')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        histories = [
            event_to_trajectory(event)
            for event in state.history.get_events(include_delegates=True)
        ]
        with open(file_path, 'w') as f:
            json.dump(histories, f)

    return state, test_result_dict
