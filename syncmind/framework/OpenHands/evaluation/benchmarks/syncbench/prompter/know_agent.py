"""
Know-everything collaborator
"""

from pandas import Series
from evaluation.utils.shared import EvalMetadata
from evaluation.benchmarks.syncbench.builds.json_util import read_json_data

class KnowPrompter:
    def __init__(
            self, 
            instance: Series, 
            metadata: EvalMetadata
        ) -> None:
        # Metadata
        self.repo_dict_path = metadata.details['repo_source_path']
        # Container
        self.container_workdir = '/workspace/test_repo'
        # Instance
        self.instance = instance
        self.instance_id = instance.instance_id
        self.func_or_method = instance.fm_type
        self.func_or_method_name = instance.fm_name
        self.original_code = instance.original_code
        self.gold_code = instance.gold_code
        self.fm_pyfile_name = instance.pyfile_name
        self.fm_pyfile_path = self.container_workdir + instance.pyfile_path.split("test_repo")[1]
        self.old_complete_context_code = instance.old_complete_context
        self.new_complete_context_code = instance.new_complete_context
        self.initial_error_log = instance.initial_error_log
        self.error_log_token_limit = 12800
        self.concise_format_initial_error()

    def concise_format_initial_error(self):
        """Concise initial"""
        repo_id = int(self.instance_id[0])
        repo_dict = read_json_data(self.repo_dict_path)
        test_method = repo_dict[repo_id-1]['test_method']
        if test_method == 'pytest':
            pytest_start_str = "==================== test session starts ===================="
            self.initial_error_log = str(self.initial_error_log)
            if pytest_start_str in self.initial_error_log:
                self.initial_error_log = pytest_start_str + self.initial_error_log.split(pytest_start_str)[1]
        
        # Input token limit: first threshold, force token number pruning
        if len(self.initial_error_log) > self.error_log_token_limit:
            self.initial_error_log = "[... (previous irrelevant log omitted)] " + self.initial_error_log[(self.error_log_token_limit-100):]

        # Input token limit: second threshold, checking and pruning if still exceeds token limit
        if len(self.initial_error_log) > self.error_log_token_limit:
            pytest_start_str = "==================== short test summary info ===================="
            if pytest_start_str in self.initial_error_log:
                self.initial_error_log = pytest_start_str + self.initial_error_log.split(pytest_start_str)[1]
            else:
                self.initial_error_log = self.initial_error_log[self.error_log_token_limit:]
                
    
    def know_everything_answerer(self, agent_question):
        # System prompt
        system_prompt_list = [
            f"""You are a helpful assistant. You are helping the user to provide question answering assistance to user's students.""",
            f"""\n\n**Grading Context:**\nIn the Python repository `test_repo` locating at `{self.container_workdir}`, there is an out-of-sync {self.func_or_method} `{self.func_or_method_name}` (denoted as `original_code`) in the Python file `{self.fm_pyfile_name}` locating at `{self.fm_pyfile_path}`. """, 
            f"""This out-of-sync `original_code` of the {self.func_or_method} `{self.func_or_method_name}` is as follows: `original_code`=\n{self.original_code}""",
            f"""\n\nThis `original_code` is out-of-sync because the Python repository `test_repo` has been updated except the {self.func_or_method} `{self.func_or_method_name}` still remains as the old-version `original_code`. Therefore, running unit test on the updated `test_repo` that contains this out-of-sync `original_code` reports the following error (denoted as `initial_execution_error`): `initial_execution_error`=\n{self.initial_error_log}\n\n""", 
            f"""\n\n**Two Questions for Students:** Running unit test on the Python repository `test_repo` (here the updated `test_repo` that contains the out-of-sync `original_code` is provided to students) reports the following error (here `initial_execution_error` is provided to students). Students need to: (1) localize the responsible function/method code that caused this error, and provide your answer of both the Python file path of the responsible function/method code and the name of the responsible function/method code, and (2) revise the responsible function/method code you just localized to fix `initial_execution_error`.""",
            f"""\n\n**Ground-truth Answers for Two Questions**\n(1) Python file path: `{self.fm_pyfile_path}`\n    Name of the responsible {self.func_or_method}: {self.func_or_method_name}\n(2) `ground_truth_revised_code`=\n{self.gold_code}""", 
            f"""\n\n**Question Answering Assistance:** To help students better answer these two questions, each student is allowed to ask you a question. However, your answer to each student's question has following restrictions:\n(1) You CAN ONLY answer the specific piece of information asked by the student, and CANNOT include any other information NOT asked by the student.\n(2) You CANNOT provide any misleading information if you are unsure of its correctness.""", 
            f"""\n\n**TO DO:** Please answer each student's question provided by the user.""", 
            f"""\n\n**Important: ** MUST give ONLY your answer as your response. MUST NOT give any other things like rhetorical questions, question analysis, enclosure symbols, etc."""
        ]
        system_prompt_string = ""
        for stc in system_prompt_list:
            system_prompt_string += stc
        # System + user
        answering_prompt_list = [
            {"role": "system", "content": system_prompt_string}, 
            {"role": "user", "content": agent_question}
        ]
        return answering_prompt_list
    