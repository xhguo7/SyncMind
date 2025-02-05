"""
Prompts for agent out-of-sync recovery
"""

import os
import pandas as pd
from evaluation.syncmind.builds.json_util import read_json_data

class Prompter(object):
    def __init__(self) -> None:
        self.func_or_method = ''
        self.func_or_method_name = ''
        self.func_or_method_file_name = ''
        self.agent_code_path = ''
        self.old_filtered_context_code = ''
        self.fm_original_code = ''
        self.initial_error_log = ''
        self.container_workspace = '/workspace/test_repo'
        self.total_credit = 0
        self.coding_cost = 0
        self.asking_cost = 0
    
    def init_prompt(self, out_of_sync_task, metadata, cost_awareness):
        self.instance_id = out_of_sync_task.instance_id
        self.func_or_method = out_of_sync_task.fm_type
        self.func_or_method_name = out_of_sync_task.fm_name
        self.func_or_method_file_name = out_of_sync_task.pyfile_name
        self.agent_code_path = self.container_workspace + out_of_sync_task.pyfile_path.split("test_repo")[1]
        self.old_filtered_context_code = out_of_sync_task.old_filtered_context
        self.fm_original_code = out_of_sync_task.original_code
        self.initial_error_log = out_of_sync_task.initial_error_log
        self.total_credit = cost_awareness['total_credit']
        self.coding_cost = cost_awareness['coding_cost']
        self.asking_cost = cost_awareness['asking_cost']
        self.max_iterations = metadata.max_iterations
        self.agent_class = metadata.agent_class
        self.repo_dict_path = metadata.details['repo_source_path']
        self.error_log_token_limit = 12800
        self.concise_format_initial_error()

    def agent_cls_suffix(self):
        """Agent suffix"""
        agent_cls_to_instance_suffix = {
            'CodeActAgent': f"""\nYou CANNOT exit this task until the USER confirm that your revised `test_repo` have passed USER's evaluation.""" + 
                            f"""\nYou CANNOT evaluate your revised `test_repo` on your own and state that `test_repo` passes USER's evaluation and exit this task. Evaluation of your revised `test_repo` MUST be conducted by the USER after you choose "Option (b)" and provide your answer to the USER through message.""" + 
                            f"""\nPlease noted that it is very unwise to run all unit tests on your side even just for testing or ckecking because other code files in `test_repo` that are irrelevant to the error log provided by the USER may currently be under USER's revision and therefore cause unit test errors. However, your task is to fix ONLY the error given by the USER.""" + 
                            f"""\nThe Python virtual environment for this task has already been set up for you and you can find the virtual environment at `/workspace/test_venv`. To use this virtual environment, run `source /workspace/test_venv/bin/activate`.""" + 
                            f"""\nNoted that the Python environment is well-prepared with all necessary dependencies installed, and therefore you CANNOT install any additional Python packages to assist your code revision.""" + 
                            f"""\nONLY when the user confirmed that your revised Python repository `test_repo` has successfully passed USER's evaluation can you end this task and run the following command to exit: <execute_bash> exit </execute_bash>."""
        }
        return agent_cls_to_instance_suffix[self.agent_class]

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
             
    
    def interactive_independent_prompter(self):
        """Independent agent out-of-sync recovery"""
        independent_instruction_list = [
            {
                "role": "system", 
                "content": f"You are a helpful assistant." + 
                           f"\n**Task:** You are generating Python code for the Python repository `test_repo` at `{self.container_workspace}` to fix the initial execution error of `test_repo` given by the USER. Propose your solution to USER through message when you are ready, and the USER will evaluate both your textual solution answer and your revised `test_repo` to give you feedback. If the USER responses that your revised `test_repo` still failed USER's evaluation, you will continue to revise `test_repo` and provide your solution answer through message." + 
                           f"""\n**Notice:**\nYour task is to revise `test_repo` to fix the initial execution error, and you MUST complete this task on your own without asking for human help. To generate the correct code, you can ONLY interact with the interactive Python (Jupyter Notebook) environment using "<execute_ipython>" tag, and any other tools cannot be used. """ + 
                           f"""\nAt each turn, you have two options (a) and (b):""" + 
                           f"""\n    (a) Interact with the Python programming environment and receive corresponding output to assist your code revision.""" + 
                           f"""\n    (b) Propose your solution, including (1) directly revising the responsible Python code of `test_repo` inside this Python repository at {self.container_workspace}, and (2) providing your textual solution answer that incorporates both the absoluate path of your revised Python file and the name of your revised function/method by sending your answer to USER through message that adheres to the required format.""" + 
                           f"""\nIf you choose "Option (a) Interaction with the Python programming environment", you should provide your textual explanation and analysis of your interaction through message, including your textual explanation of both your execution command and the environment output, which should be enclosed using "<env>" tag, for example: <env> I used the command "ls" to locate the responsible Python code. </env>""" + 
                           f"""\nOn the other hand, if you choose "Option (b) Provide your solution", you should:""" + 
                           f"""\n    (1) Revise the responsible Python code of `test_repo` with proper indentation, which should be directly implemented inside the Python repository at `{self.container_workspace}`.""" + 
                           f"""\n    (2) Provide the absolute path of your revised Python file and the name of your revised function/method as your solution by sending your solution answer to USER through message, which MUST contain ONLY one line of the absolute path followed by another line of the function/method name without any other texts and be enclosed using "<text>" tag, for example: <text> /workspace/test_repo/src/run_inference.py\ninference_prepare </text>. If you revised a method code, MUST provide ONLY the name of your revised method and MUST NOT provide the name of the Python class containing your revised method (e.g., `inference_prepare` is the name of your revised method, but NOT the Python class). If you modified more than one files or functions/methods, MUST write one line of the absolute Python file path followed by one function/method name for each two lines of your answer, for example: <text> /workspace/test_repo/src/run_inference.py\ninference_prepare\n/workspace/test_repo/src/run_inference.py\ninference_util </text>.""" + 
                           f"""\nEither you choose to `(a) Interact with the Python environment` or `(b) Propose your solution`, you MUST send a message to the USER to evaluate your solution and provide feedback.""" + 
                           f"""\n**Important Rules** {self.agent_cls_suffix()}""" + 
                           f"""\n**Important Notice** In the beginning, you have an initial budget of ${self.total_credit}. Before correctly propose a solution, each of your `(b) Proposing a solution` attempts costs ${self.coding_cost}. Meanwhile, although you may make as many `(a) Python environment interaction` attempts as you want at no cost, you have in total {self.max_iterations} attempts to complete this task. You will fail this task if you use up all your ${self.total_credit} budget or reach the maximum {self.max_iterations}-attempt limit without generating a correct `(b) Proposing a solution` response. Therefore, please arrange each of your actions wisely."""
            },
            {
                "role": "user", 
                "content": f"[Budget: ${self.total_credit}] Your revised `test_repo` failed execution test as follows:\n[initial execution error]\n{self.initial_error_log}"
            }
        ]

        independent_instruction_string = ""
        independent_instruction_string += f"SYSTEM:\n{independent_instruction_list[0]['content']}\n\n"
        independent_instruction_string += f"USER:\n{independent_instruction_list[1]['content']}\n\n"

        return independent_instruction_string
    
    def interactive_collaborative_prompter(self):
        """Collaborative agent out-of-sync recovery"""
        collaborative_instruction_list = [
            {
                "role": "system", 
                "content": f"You are a helpful assistant." + 
                           f"\n**Task:** You are generating Python code for the Python repository `test_repo` at `{self.container_workspace}` to fix the initial execution error of `test_repo` given by the USER. Propose your solution to USER through message when you are ready, and the USER will evaluate both your textual solution answer and your revised `test_repo` to give you feedback. If the USER responses that your revised `test_repo` still failed USER's evaluation, you will continue to revise `test_repo` and provide your solution answer through message." + 
                           f"""\n**Notice:**\nYour task is to revise `test_repo` to fix the initial execution error, and you may ask for human help. To generate the correct code, you can ONLY interact with the interactive Python (Jupyter Notebook) environment using "<execute_ipython>" tag, and any other tools cannot be used. """ + 
                           f"""\nAt each turn, you have three options (a), (b), and (c):""" + 
                           f"""\n    (a) Interact with the Python programming environment and receive corresponding output to assist your code revision.""" + 
                           f"""\n    (b) Propose your solution, including (1) directly revising the responsible Python code of `test_repo` inside this Python repository at {self.container_workspace}, and (2) providing your textual solution answer that incorporates both the absoluate path of your revised Python file and the name of your revised function/method by sending your answer to USER through message that adheres to the required format.""" + 
                           f"""\n    (c) Ask human a question and receive the corresponding answer to assist your code revision.""" + 
                           f"""\nIf you choose "Option (a) Interaction with the Python programming environment", you should provide your textual explanation and analysis of your interaction through message, including your textual explanation of both your execution command and the environment output, which should be enclosed using "<env>" tag, for example: <env> I used the command "ls" to locate the responsible Python code. </env>""" + 
                           f"""\nIf you choose "Option (b) Propose your solution", you should:""" + 
                           f"""\n    (1) Revise the responsible Python code of `test_repo` with proper indentation, which should be directly implemented inside the Python repository at `{self.container_workspace}`.""" + 
                           f"""\n    (2) Provide the absolute path of your revised Python file and the name of your revised function/method as your solution by sending your solution answer to USER through message, which MUST contain ONLY one line of the absolute path followed by another line of the function/method name without any other texts and be enclosed using "<text>" tag, for example: <text> /workspace/test_repo/src/run_inference.py\ninference_prepare </text>. If you revised a method code, MUST provide ONLY the name of your revised method and MUST NOT provide the name of the Python class containing your revised method (e.g., `inference_prepare` is the name of your revised method, but NOT the Python class). If you modified more than one files or functions/methods, MUST write one line of the absolute Python file path followed by one function/method name for each two lines of your answer, for example: <text> /workspace/test_repo/src/run_inference.py\ninference_prepare\n/workspace/test_repo/src/run_inference.py\ninference_util </text>.""" + 
                           f"""\nIf you choose "Option (c) Ask for human assistance", you should provide your question through message, which should be enclosed using "<question>" tag and started with "[QUESTION]", for example: <question> [QUESTION] What programming languages are used in `test_repo`? </question>.""" + 
                           f"""\nNo matter which option you choose among (a) (b) and (c), you MUST send a message to the USER to evaluate your response and provide feedback.""" + 
                           f"""\n**Important Rules** {self.agent_cls_suffix()}""" + 
                           f"""\n**Important Notice** In the beginning, you have an initial budget of ${self.total_credit}. Before correctly propose a solution, each of your `(b) Proposing a solution` attempts costs ${self.coding_cost}, while each of your `(c) Asking for human's assistance` attempts costs ${self.asking_cost}. Meanwhile, although you may make as many `(a) Python environment interaction` attempts as you want at no cost, you have in total {self.max_iterations} attempts to complete this task. You will fail this task if you use up all your ${self.total_credit} balance or reach the maximum {self.max_iterations}-attempt limit without generating a correct `(b) Proposing a solution` response. Therefore, please arrange each of your actions wisely. """ + 
                           f"""\n**Tips** Try `(c) Ask human a question` at any turns! This can definitely help accelerate your progress of proposing a correct solution and complete your task!"""
            },
            {
                "role": "user", 
                "content": f"[Budget: ${self.total_credit}] Your revised `test_repo` failed execution test as follows:\n[initial execution error]\n{self.initial_error_log}"
            }
        ]

        collaborative_instruction_string = ""
        collaborative_instruction_string += f"SYSTEM:\n{collaborative_instruction_list[0]['content']}\n\n"
        collaborative_instruction_string += f"USER:\n{collaborative_instruction_list[1]['content']}\n\n"
    
        return collaborative_instruction_string
