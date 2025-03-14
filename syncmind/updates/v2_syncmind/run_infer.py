"""
Agent out-of-sync recovery
"""

import os
import json
import toml
import asyncio
import pandas as pd
from typing import Any

from evaluation.benchmarks.syncmind.builds.mapping import (
    get_instance_resource_factor,
)
from evaluation.utils.shared import (
    EvalException,
    EvalMetadata,
    EvalOutput,
    assert_and_raise,
    get_default_sandbox_config_for_eval,
    get_metrics,
    is_fatal_evaluation_error,
    make_metadata,
    prepare_dataset,
    reset_logger_for_multiprocessing,
    run_evaluation,
    update_llm_config_for_completions_logging,
)
from openhands.core.config import (
    AppConfig,
    AgentConfig,
    get_llm_config_arg,
    get_parser,
)
from openhands.core.logger import openhands_logger as logger
from openhands.events.action import CmdRunAction, MessageAction
from openhands.events.observation import CmdOutputObservation
from openhands.events.serialization.event import event_to_dict
from openhands.runtime.base import Runtime
from openhands.core.main import create_runtime
from evaluation.benchmarks.syncmind.runs.resync_run import run_controller
from evaluation.benchmarks.syncmind.prompter.recover_prompt import Prompter
from evaluation.benchmarks.syncmind.prompter.user_response import codeact_user_response_resync
from evaluation.benchmarks.syncmind.builds.instance import InstanceProcessor
from evaluation.benchmarks.syncmind.builds.json_util import read_json_data
from evaluation.benchmarks.syncmind.builds.config import SyncMindConfig
from evaluation.benchmarks.syncmind.evals.evaluator import DockerManager
from evaluation.benchmarks.syncmind.builds.prep import container_init_for_instance

USE_HINT_TEXT = os.environ.get('USE_HINT_TEXT', 'false').lower() == 'true'
USE_INSTANCE_IMAGE = os.environ.get('USE_INSTANCE_IMAGE', 'false').lower() == 'true'
RUN_WITH_BROWSING = os.environ.get('RUN_WITH_BROWSING', 'false').lower() == 'true'

AGENT_CLS_TO_FAKE_USER_RESPONSE_FN = {
    'CodeActAgent': codeact_user_response_resync
}

WORKSPACE_DIR = Prompter().container_workspace


def get_instruction(instance: pd.Series, metadata: EvalMetadata):
    instance_prompter = Prompter()
    instance_prompter.init_prompt(instance, metadata, RESOURCE_AWARENESS)
    if resync_method == 'independent':
        instruction = instance_prompter.interactive_independent_prompter()
    else:  # collaborative
        instruction = instance_prompter.interactive_collaborative_prompter()
    return instruction

def get_config(
    instance: pd.Series,
    metadata: EvalMetadata
) -> AppConfig:
    RESYNC_CONTAINER_IMAGE = f"xuehang/{instance.instance_id.split('__')[0]}:3.11"

    if os.environ.get('ALLHANDS_API_KEY', None) != None:
        global REMOTE_RUNTIME
        REMOTE_RUNTIME = True
        RESYNC_CONTAINER_IMAGE = "docker.io/xuehang/" + RESYNC_CONTAINER_IMAGE
    
    base_container_image = RESYNC_CONTAINER_IMAGE
    logger.info(f"Using out-of-sync recovery container image: {RESYNC_CONTAINER_IMAGE}")

    docker_manager = DockerManager(instance)
    image_id = docker_manager.check_docker_image()

    sandbox_config = get_default_sandbox_config_for_eval()
    sandbox_config.base_container_image = base_container_image
    sandbox_config.enable_auto_lint = True
    sandbox_config.use_host_network = False
    sandbox_config.timeout = 300
    # Add platform to the sandbox config to solve issue 4401
    sandbox_config.platform = 'linux/amd64'
    sandbox_config.remote_runtime_resource_factor = get_instance_resource_factor(
        dataset_name=metadata.dataset,
        instance_id=instance['instance_id'],
    )
    sandbox_config.keep_runtime_alive = False
    sandbox_config.api_key = os.environ.get('ALLHANDS_API_KEY', None)
    sandbox_config.remote_runtime_api_url = os.environ.get('SANDBOX_REMOTE_RUNTIME_API_URL')

    config = AppConfig(
        default_agent=metadata.agent_class,
        run_as_openhands=False,
        max_budget_per_task=4,
        max_iterations=metadata.max_iterations,
        sandbox=sandbox_config,
        # do not mount workspace
        workspace_base=None,
        workspace_mount_path=None,
    )

    config.set_llm_config(
        update_llm_config_for_completions_logging(
            metadata.llm_config, metadata.eval_output_dir, instance['instance_id']
        )
    )
    agent_config = AgentConfig(
        codeact_enable_jupyter=False,
        codeact_enable_browsing=RUN_WITH_BROWSING,
        codeact_enable_llm_editor=False,
        condenser=metadata.condenser_config,
        enable_prompt_extensions=False,
    )
    config.set_agent_config(agent_config)
    return config



def initialize_runtime(
    runtime: Runtime,
    instance: pd.Series,
    metadata: EvalMetadata,
):
    """Initialize the runtime for the agent.

    This function is called before the runtime is used to run the agent.
    """
    logger.info('-' * 50)
    logger.info('BEGIN Runtime Initialization Fn')
    logger.info('-' * 50)
    obs: CmdOutputObservation

    # Container init for current instance
    container_init_for_instance(runtime, instance, metadata)

    # Set instance id
    action = CmdRunAction(
        command=f"""echo 'export INSTANCE_ID={instance['instance_id']}' >> ~/.bashrc && echo 'export PIP_CACHE_DIR=~/.cache/pip' >> ~/.bashrc && echo "alias git='git --no-pager'" >> ~/.bashrc"""
    )
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0, f'Failed to export INSTANCE_ID: {obs.content}'
    )

    action = CmdRunAction(command="""export USER=$(whoami); echo USER=${USER} """)
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to export USER: {obs.content}')

    action = CmdRunAction(command='cat ~/.bashrc')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to cat ~/.bashrc: {obs.content}')
    
    action = CmdRunAction(command='source ~/.bashrc')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0, f'Failed to source ~/.bashrc: {obs.content}'
    )

    action = CmdRunAction(command='source /workspace/test_venv/bin/activate')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    logger.info(f"Test venv activation: {obs.content}")
    
    action = CmdRunAction(command=f'ls')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0,
        f'Failed to ls',
    )

    action = CmdRunAction(command=f'cd {WORKSPACE_DIR}')
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(
        obs.exit_code == 0,
        f'Failed to cd to {WORKSPACE_DIR}: {obs.content}',
    )
    
    if not REMOTE_RUNTIME:
        action = CmdRunAction(command='git reset --hard')
        logger.info(action, extra={'msg_type': 'ACTION'})
        obs = runtime.run_action(action)
        logger.info(obs, extra={'msg_type': 'OBSERVATION'})
        assert_and_raise(obs.exit_code == 0, f'Failed to git reset --hard: {obs.content}')
    
    action = CmdRunAction(
        command='for remote_name in $(git remote); do git remote remove "${remote_name}"; done'
    )
    logger.info(action, extra={'msg_type': 'ACTION'})
    obs = runtime.run_action(action)
    logger.info(obs, extra={'msg_type': 'OBSERVATION'})
    assert_and_raise(obs.exit_code == 0, f'Failed to remove git remotes: {obs.content}')

    logger.info('-' * 50)
    logger.info('END Runtime Initialization Fn')
    logger.info('-' * 50)



def process_instance(
    instance: pd.Series,
    metadata: EvalMetadata,
    reset_logger: bool = True
) -> EvalOutput:
    
    # Init test_result_dict for current instance
    test_result_dict_save_path = metadata.details['output_save_path'] + f'test_result_dict_instance_{instance.instance_id}.json'
    test_result_dict = read_json_data(test_result_dict_save_path)
    test_result_dict[instance.instance_id] = {}
    
    # Config instance
    config = get_config(instance, metadata)
    instruction = get_instruction(instance, metadata)
    
    # Setup the logger properly, so you can run multi-processing to parallelize the evaluation
    if reset_logger:
        log_dir = os.path.join(metadata.eval_output_dir, 'infer_logs')
        reset_logger_for_multiprocessing(logger, instance.instance_id, log_dir)
    else:
        logger.info(f'Starting evaluation for instance {instance.instance_id}.')
    
    # Start runtime
    runtime = create_runtime(config)

    try:
        initialize_runtime(runtime, instance, metadata)

        # Here's how you can run the agent (similar to the `main` function) and get the final task state
        state, test_result_dict = asyncio.run(
            run_controller(
                config=config,
                instruction=instruction,
                initial_user_action=MessageAction(content=instruction),
                instance=instance,
                workspace_dir=WORKSPACE_DIR,
                metadata=metadata, 
                runtime=runtime
            )
        )

        # if fatal error, throw EvalError to trigger re-run
        if is_fatal_evaluation_error(state.last_error):
            raise EvalException('Fatal error detected: ' + state.last_error)

        logger.info(f"{'-' * 15} Agent out-of-sync recovery evaluation result for instance {instance.instance_id} {'-' * 15}")
        logger.info(test_result_dict[instance.instance_id]['final_instance_eval_result'])
        logger.info(f"{'-' * 30} Final Eval Output End {'-' * 30}")

    finally:
        runtime.close()

    # If you are working on some simpler benchmark that only evaluates the final model output (e.g., in a MessageAction)
    # # You can simply get the LAST `MessageAction` from the returned `state.history` and parse it for evaluation.
    if state is None:
        raise ValueError('State should not be None.')
        
    # Get histories & metrics
    histories = [event_to_dict(event) for event in state.history]
    metrics = get_metrics(state)
    
    task_state = None
    if 'task_state' in state.extra_data:
        task_state = state.extra_data['task_state']
        logger.info('Task state: ' + str(task_state.to_dict()))
    
    # Save the output
    output = EvalOutput(
        instance_id=instance.instance_id,
        instruction=instruction,
        instance=instance.to_dict(),
        test_result=test_result_dict,
        metadata=metadata,
        history=histories,
        metrics=metrics,
        error=state.last_error if state and state.last_error else None,
    )
    
    # Clean up local tmp test_repo dir
    inst_processor = InstanceProcessor(instance)
    inst_processor.instance_tmp_clean_up()
    
    return output


if __name__ == '__main__':
    """SyncMind: Agent out-of-sync recovery"""    
    parser = get_parser()
    parser.add_argument(
        '--resync-method',
        type=str,
        default='independent',
        help='Agent out-of-sync recovery method: independent | collaborative',
        choices=['independent', 'collaborative']
    )
    parser.add_argument(
        '--total-budget',
        type=int,
        default=1000,
        help='Total hypothetical budget allowed for agent out-of-sync recovery'
    )
    parser.add_argument(
        '--coding-cost',
        type=int,
        default=100,
        help='The hypothetical cost of proposing a solution'
    )
    parser.add_argument(
        '--asking-cost',
        type=int,
        default=100,
        help='The hypothetical cost of proactively asking collaborator assistance'
    )
    parser.add_argument(
        '--remote-runtime',
        type=str,
        default='false',
        help='Whether to use remote runtime for agent out-of-sync recovery evaluation (true: True | false: False)',
        choices=["true", "false"]
    )
    parser.add_argument(
        '--data-path',
        type=str,
        default=None,
        help='(Optional) Path to the dataset that you would like to run SyncMind on, if you would like to run SyncMind on local data'
    )
    args, _ = parser.parse_known_args()

    # If remote runtime
    REMOTE_RUNTIME = True if args.remote_runtime == "true" else False    

    # Resource awareness
    RESOURCE_AWARENESS = {
        'total_budget': args.total_budget, 
        'coding_cost': args.coding_cost,
        'asking_cost': args.asking_cost
    }
    
    # Load data
    if (args.data_path != "None") and (args.data_path != None):
        instance_dataset_path = args.data_path
        instance_data = pd.read_csv(instance_dataset_path)
    else:
        from datasets import load_dataset
        syncbench_datasets = load_dataset("xuehang/SyncBench", data_files={
            "syncbench_300": "syncbench/syncbench_300.csv",
            "syncbench_300_caller": "syncbench/syncbench_300_caller.csv",
            "syncbench_300_callee": "syncbench/syncbench_300_callee.csv"
        })
        instance_data = syncbench_datasets["syncbench_300"].to_pandas()
        instance_dataset_path = "xuehang/SyncBench/syncbench/syncbench_300"
    
    if args.eval_n_limit > len(instance_data):
        args.eval_n_limit = len(instance_data)
    
    # Basic config
    resync_method = args.resync_method  # independent or collaborative
    logger.info(f"Out-of-sync Recovery: {len(instance_data)} instances for {resync_method} recovery  |  Current task: {args.eval_n_limit} instances")
    
    llm_config = None
    if args.llm_config:
        llm_config = get_llm_config_arg(args.llm_config)
    
    if llm_config is None:
        raise ValueError(f'Could not find LLM config: --llm_config {args.llm_config}')
    
    # Init configuration
    syncmind_configer = SyncMindConfig()
    syncmind_configer.init_instance_path(instance_dataset_path, resync_method, RESOURCE_AWARENESS, args.max_iterations, args.llm_config)
    syncmind_configer.check_create_dir(syncmind_configer.resync_output_save_dir)
    
    # Resource awareness
    logger.info("---------- Resource Awareness ----------")
    logger.info(f"        Max-turn Limit:  {args.max_iterations} turns")
    logger.info(f"        Budget:          ${RESOURCE_AWARENESS['total_budget']}")
    logger.info(f"        Coding Cost:     ${RESOURCE_AWARENESS['coding_cost']}")
    if resync_method == "collaborative": 
        logger.info(f"        Asking Cost:     ${RESOURCE_AWARENESS['asking_cost']}")
    logger.info("---------- Resource Awareness ----------")

    details = {
        'resync_method': resync_method,
        'total_budget': RESOURCE_AWARENESS['total_budget'], 
        'coding_cost': RESOURCE_AWARENESS['coding_cost'], 
        'asking_cost': RESOURCE_AWARENESS['asking_cost'],  # will not be used and can be any number if resync_method='independent'
        'repo_source_path': syncmind_configer.resync_data_source_path, 
        'output_save_path': syncmind_configer.resync_output_save_dir,
        'workspace_dir': WORKSPACE_DIR,
        'instance_dataset_path': instance_dataset_path,
        'if_remote': REMOTE_RUNTIME
    }
    
    metadata = make_metadata(
        llm_config=llm_config,
        dataset_name=f"syncmind_{resync_method}_{instance_dataset_path.split('/')[-1].replace('_instance.csv', '').replace('.csv', '')}",
        agent_class=args.agent_cls,
        max_iterations=args.max_iterations,
        eval_note=args.eval_note,
        eval_output_dir=syncmind_configer.resync_output_save_dir,
        details=details
    )

    output_file = os.path.join(metadata.eval_output_dir, 'output.jsonl')
    instances = prepare_dataset(instance_data, output_file, args.eval_n_limit)

    run_evaluation(
        instances,
        metadata,
        output_file,
        args.eval_num_workers,
        process_instance,
        timeout_seconds=120 * 60,  # 2 hour PER instance should be more than enough
        max_retries=5,
    )
    
    # Remove after use
    instance_series = instances.iloc[0].squeeze()
    docker_manager = DockerManager(instance_series)
    docker_manager.remove_tmp_dirs()
    # docker_manager.remove_docker_image()

    # Remove tmp dirs after use: comment out if run multiple processes in parallel
    # syncmind_configer.remove_tmp_dir()
    