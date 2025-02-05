"""
Align agent code to context code
"""

import ast
import autopep8
from utils.logger import logger


def correct_indentation(code: str) -> str:
    """Python code format correction"""
    try:
        corrected_code = autopep8.fix_code(code, options={'indent_size': 4})
        return corrected_code
    except Exception as e:
        logger.warning(f"[Invalid Code Format Correction] An error occurred:\n{e}\nDirectly returning original code...")
        return code
    
def remove_leading_spaces(input_str: str) -> str:
    """Remove leading blank spaces"""
    first_char_index = len(input_str) - len(input_str.lstrip(' '))
    output_str = input_str[first_char_index:]
    return output_str

def extract_function_name(input_code: str) -> str:
    """
    Args:
    - input_code (str): The Python code containing the function.
    
    Returns:
    - str: The name of the function, or None if the function cannot be parsed.
    """
    try:
        parsed_code = ast.parse(input_code)
    except SyntaxError:
        return None
    
    for node in ast.walk(parsed_code):
        if isinstance(node, ast.FunctionDef):
            return node.name

    return None

def align_agent_context(agent_code: str, context_code: str) -> str:
    func_name = extract_function_name(agent_code)
    if not func_name:
        return agent_code
    
    aligned_agent_code = ""
    align_in_progress_flag, if_aligned_flag = False, False
    
    line_count = 0
    for context_code_line in context_code.split('\n'):
        line_count += 1
        if (if_aligned_flag == False) and (f"def {func_name}" in context_code_line):
            num_leading_spaces = len(context_code_line) - len(context_code_line.lstrip())
            leading_spaces = num_leading_spaces * ' '
            for agent_code_line in agent_code.split('\n'):
                aligned_agent_code += (leading_spaces + agent_code_line + '\n')
            align_in_progress_flag, if_aligned_flag = True, True
            continue

        if align_in_progress_flag == True:
            if context_code_line.replace(' ', '') == '':
                if line_count == len(context_code.split('\n')):
                    align_in_progress_flag = False
                    aligned_agent_code += '\n'
                    break

                next_context_line = context_code.split('\n')[line_count]
                if next_context_line.replace(' ', '') == '':
                    continue

                next_line_leading_spaces_num = len(next_context_line) - len(next_context_line.lstrip())
                if next_line_leading_spaces_num <= num_leading_spaces:
                    align_in_progress_flag = False
                    aligned_agent_code += '\n'
        
        if align_in_progress_flag == False:
            aligned_agent_code += (context_code_line + '\n')

    if if_aligned_flag == False:
        logger.warning(f"[Warning] Function/method `{func_name}` is not found in the context_code. Will return the original context file.")
    else: 
        logger.info(f"Successfully found and replaced the code of function/method `{func_name}` in the context_code.")

    return correct_indentation(aligned_agent_code)
