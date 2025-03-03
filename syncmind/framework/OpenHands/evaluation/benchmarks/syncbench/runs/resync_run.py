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

from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.core.loop import run_agent_until_done
from openhands.core.schema import AgentState
from openhands.core.main import load_replay_log
from openhands.core.setup import (
    create_agent,
    create_controller,
    create_runtime,
    generate_sid,
)
from openhands.events import EventSource, EventStreamSubscriber
from openhands.events.action import (
    AgentDelegateAction,
    AgentFinishAction,
    CmdRunAction,
    IPythonRunCellAction,
    MessageAction,
    NullAction
)
from openhands.events.action.action import Action
from openhands.events import EventSource, EventStream, EventStreamSubscriber
from openhands.events.event import Event
from openhands.events.observation import AgentStateChangedObservation
from openhands.events.serialization.event import event_to_trajectory
from openhands.llm.llm import LLM
from openhands.runtime import get_runtime_cls
from openhands.runtime.base import Runtime
from openhands.storage import get_file_store
from evaluation.utils.shared import EvalMetadata
from evaluation.benchmarks.syncbench.runs.final_eval import complete_runtime
from evaluation.benchmarks.syncbench.runs.runtime_complete import complete_runtime_eval
from evaluation.benchmarks.syncbench.builds.prep import container_init_for_instance
from evaluation.benchmarks.syncbench.runs.runtime_response import (
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
        initial_user_action: An Action object containing initial user input
        sid: (optional) The session id. IMPORTANT: please don't set this unless you know what you're doing.
            Set it to incompatible value will cause unexpected behavior on RemoteRuntime.
        runtime: (optional) A runtime for the agent to run on.
        agent: (optional) A agent to run.
        exit_on_message: quit if agent asks for a message from user (optional)
        fake_user_response_fn: An optional function that receives the current state
            (could be None) and returns a fake user response.
        headless_mode: Whether the agent is run in headless mode.

    Returns:
        The final state of the agent, or None if an error occurred.

    Raises:
        AssertionError: If initial_user_action is not an Action instance.
        Exception: Various exceptions may be raised during execution and will be logged.

    Notes:
        - State persistence: If config.file_store is set, the agent's state will be
          saved between sessions.
        - Trajectories: If config.trajectories_path is set, execution history will be
          saved as JSON for analysis.
        - Budget control: Execution is limited by config.max_iterations and
          config.max_budget_per_task.

    Example:
        >>> config = load_app_config()
        >>> action = MessageAction(content="Write a hello world program")
        >>> state = await run_controller(config=config, initial_user_action=action)
    """
    # make sure the session id is set
    sid = sid or generate_sid(config)

    if agent is None:
        agent = create_agent(config)

    if runtime is None:
        runtime = create_runtime(
            config,
            sid=sid,
            headless_mode=headless_mode,
            agent=agent,
            selected_repository=config.sandbox.selected_repo,
        )

    event_stream = runtime.event_stream

    replay_events: list[Event] | None = None
    if config.replay_trajectory_path:
        logger.info('Trajectory replay is enabled')
        assert isinstance(initial_user_action, NullAction)
        replay_events, initial_user_action = load_replay_log(
            config.replay_trajectory_path
        )

    controller, initial_state = create_controller(
        agent, runtime, config, replay_events=replay_events
    )

    assert isinstance(
        initial_user_action, Action
    ), f'initial user actions must be an Action, got {type(initial_user_action)}'
    logger.debug(
        f'Agent Controller Initialized: Running agent {agent.name}, model '
        f'{agent.llm.config.model}, with actions: {initial_user_action}'
    )

    if initial_state == None:
        controller.get_state().extra_data = metadata.details
        controller.get_state().extra_data['current_balance'] = metadata.details['total_budget']
        controller.get_state().extra_data['env_turn'] = 0
        controller.get_state().extra_data['coding_turn'] = 0
        controller.get_state().extra_data['asking_turn'] = 0

    # Env init
    container_init_for_instance(runtime, instance, metadata)

    assert isinstance(
        initial_user_action, Action
    ), f'initial user actions must be an Action, got {type(initial_user_action)}'
    # Logging
    logger.debug(
        f'Agent Controller Initialized: Running agent {agent.name}, model '
        f'{agent.llm.config.model}, with actions: {initial_user_action}'
    )

    # start event is a MessageAction with the task, either resumed or new
    if initial_state is not None:
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
    else:
        # init with the provided actions
        event_stream.add_event(initial_user_action, EventSource.USER)

    def on_event(event: Event):
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
                    state = controller.get_state()
                    return state, test_result_dict
                
                # If still have enough balance
                action = MessageAction(content=message)
                event_stream.add_event(action, EventSource.USER)

        else:
            controller.get_state().extra_data['env_turn'] += 1
            if len(controller.get_state().history) > 0:
                last_event = controller.get_state().history[-1]
                if isinstance(last_event, IPythonRunCellAction):
                    save_current_turn_ipythonaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                elif isinstance(last_event, CmdRunAction):
                    save_current_turn_cmdaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                else:
                    if event.source == 'agent':
                        if isinstance(last_event, AgentFinishAction):
                            save_current_turn_finishaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                        elif isinstance(last_event, MessageAction):
                            message = save_current_turn_othermessageaction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                        else:
                            message = save_current_turn_otheraction(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata)
                            action = MessageAction(content=message)
                            event_stream.add_event(action, EventSource.USER)
    
    event_stream.subscribe(EventStreamSubscriber.MAIN, on_event, sid)

    end_states = [
        AgentState.FINISHED,
        AgentState.REJECTED,
        AgentState.ERROR,
        AgentState.PAUSED,
        AgentState.STOPPED,
    ]
    
    try:
        await run_agent_until_done(controller, runtime, end_states)
    except Exception as e:
        logger.error(f'Exception in main loop: {e}')
    
    # save session when we're about to close
    if config.file_store is not None and config.file_store != 'memory':
        end_state = controller.get_state()
        # NOTE: the saved state does not include delegates events
        end_state.save_to_session(event_stream.sid, event_stream.file_store)

    # Final evaluation to complete runtime before close
    test_result = complete_runtime(runtime, instance, workspace_dir)
    test_result_dict = complete_runtime_eval(controller.get_state(), runtime, instruction, instance, workspace_dir, metadata, test_result)
    
    # Get state when done
    state = controller.get_state()
    
    # save trajectories if applicable
    if config.save_trajectory_path is not None:
        # if save_trajectory_path is a folder, use session id as file name
        if os.path.isdir(config.save_trajectory_path):
            file_path = os.path.join(config.save_trajectory_path, sid + '.json')
        else:
            file_path = config.save_trajectory_path
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        histories = [event_to_trajectory(event) for event in state.history]
        with open(file_path, 'w') as f:
            json.dump(histories, f)

    return state, test_result_dict
