"""
User response
"""

import pandas as pd
from openhands.controller.state.state import State
from openhands.core.logger import openhands_logger as logger
from openhands.events.action.message import MessageAction


def check_if_out_of_balance(
        instance: pd.Series,
        test_result: dict
    ) -> bool:
    """Check if running out of balance"""
    current_balance = test_result['current_balance']

    # If running out of balance
    if test_result['resync_method'] == 'independent':
        if current_balance < test_result['coding_cost']:
            logger.info(f"[Failed] Agent out-of-sync {test_result['resync_method']} recovery failed for Instance `{instance.instance_id}` due to running out of balance.")
            return True  # failed due to running out of balance
        else: 
            return False
    else:  # collaborative
        if current_balance < min(test_result['coding_cost'], test_result['asking_cost']):
            logger.info(f"[Failed] Agent out-of-sync {test_result['resync_method']} recovery failed for Instance `{instance.instance_id}` due to running out of balance.")
            return True  # failed due to running out of balance
        else: 
            return False

def check_progress(
        instance: pd.Series,
        test_result: dict
    ) -> str:
    """Check out-of-sync recovery progress"""
    if check_if_out_of_balance(instance, test_result):
        return 'out-of-balance'
    
    if test_result['adapt_grade'] == 1:
        return 'success'
    else: 
        return 'continue'


def codeact_user_response_resync(
    state: State, 
    instance: pd.Series,
    test_result: dict, 
    unittest_result: dict
) -> str:
    """User response"""
    if test_result:
        current_balance = test_result['current_balance']

        if unittest_result['adapt_grade'] == 1:
            test_comment = f"Well done! Your revised `test_repo` has successfully passed USER's evaluation test! Please reply the following command to end this task: <execute_bash> exit </execute_bash>."
            msg = (
                f'[Balance: ${current_balance} Left] {test_comment}'
            )
        else:
            test_comment = f"Your revised `test_repo` still failed USER's evaluation test."
            if check_if_out_of_balance(instance, test_result):  # if running out of balance
                msg = (
                    f'[Balance: ${current_balance} Left] {test_comment} '
                    f'\nUnfortunately, you are running out of budget. Please directly run the following command to exit: <execute_bash> exit </execute_bash>.'
                )
            else: 
                msg = (
                    f'[Balance: ${current_balance} Left] {test_comment} '
                    f'Please try again.'
                )
    
    else:
        msg = f"[Balance: ${current_balance} Left] Please try again."
        
    return msg
