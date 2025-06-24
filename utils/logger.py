"""
Logger definition
"""

import os
import json
import datetime
import inspect


# Dataset construction logger
class ConstructLogger:
    # Initialize
    def __init__(self, log_file_path: str) -> None:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
        # Configure logging
        self.log_file_path = log_file_path
        self.log_dict_list = []
        self.log_idx = 0
    
    # Create current log
    def collect_log_info(self, commit_id, fm_name, fm_file, test_file, original_exe_result, gold_exe_result, test_type):
        self.log_idx += 1
        new_log = {
            'log_id': self.log_idx, 
            'commit_id': commit_id,
            'fm_name': fm_name,
            'fm_file': fm_file, 
            'test_file': test_file,
            'exe_result': {
                'test_type': test_type,
                'original_fm': {
                    'returncode': original_exe_result.returncode, 
                    'stdour': original_exe_result.stdout, 
                    'stderr': original_exe_result.stderr
                }, 
                'gold_fm': {
                    'returncode': gold_exe_result.returncode, 
                    'stdour': gold_exe_result.stdout, 
                    'stderr': gold_exe_result.stderr
                }
            }
        }
        self.log_dict_list += [new_log]
        self.write_to_log()
        
    def write_to_log(self):
        with open(self.log_file_path, "w") as log_file:
            json.dump(self.log_dict_list, log_file, indent=4)
        print(f"Successfully save log to {self.log_file_path}")


# Out-of-sync recovery logger
class RecoverLogger(ConstructLogger):
    def __init__(self, log_file_path):
        super().__init__(log_file_path)

    # Create current log
    def colloect_recovery_log_info(
            self, 
            commit_id: str, 
            fm_name: str, 
            fm_file: str, 
            test_file: str, 
            original_exe_result: str, 
            gold_exe_result: str, 
            test_type: str
        ):
        self.log_idx += 1
        new_log = {
            'log_id': self.log_idx, 
            'commit_id': commit_id,
            'fm_name': fm_name,
            'fm_file': fm_file, 
            'test_file': test_file,
            'exe_result': {
                'test_type': test_type,
                'original_fm': {
                    'returncode': original_exe_result.returncode, 
                    'stdour': original_exe_result.stdout, 
                    'stderr': original_exe_result.stderr
                }, 
                'gold_fm': {
                    'returncode': gold_exe_result.returncode, 
                    'stdour': gold_exe_result.stdout, 
                    'stderr': gold_exe_result.stderr
                }
            }
        }
        self.log_dict_list += [new_log]
        self.write_to_log()


class Logger:
    def __init__(
        self
        ) -> None:
        self.hex_color_dict = {
            "content": "#000000",   # black
            "info": "#00ff00",  # green
            "success": "#00ff00",  # green
            "warning": "#ffff00",  # yellow
            "testing": "#0598FF",  # blue
            "error": "#ff0000",
            "yellow_light": "#FFFCA3",
            "pink_light": "#FFD1EA",
            "cyan_light": "#ADEEE1",
            "green_light": "#90E9AF",
            "blue_light": "#91D2FF",
            "cyan": "#30C0B4",
            "red": "#F85C63",
            "green": "#27BF60",
            "blue": "#0598FF",
        }
        self.write_path = os.path.join(os.path.dirname(os.path.abspath(__file__)).split('utils')[0], 'logs', 'syncmind_logs.txt')
        self.auto_write = True
        self._init_logs()

    def _init_logs(self):
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)).split('utils')[0], 'logs')
        os.makedirs(log_dir, exist_ok = True)

    def write(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"

        # Write to save
        with open(self.write_path, 'a+') as file:
            file.write(f"\n{msg_detail}\n{msg}\n")
    
    def _auto_write(self, msg_with_detail: str) -> None:
        if self.auto_write:
            # Write to save
            with open(self.write_path, 'a+') as file:
                file.write(f"\n{msg_with_detail}\n")

    # Show plain print
    def pinfo(self, msg: str) -> None:
        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    # Exposed public method to print an info message
    def info(self, msg: str) -> None:
        self._info(msg)

    # Exposed public method to print a success message
    def success(self, msg: str) -> None:
        self._success(msg)

    # Exposed public method to print an error message
    def error(self, msg: str) -> None:
        self._error(msg)

    # Exposed public method to print an warning message
    def warning(self, msg: str) -> None:
        self._warning(msg)

    # Exposed public method to print an testing output
    def testing(self, msg: str) -> None:
        self._testing(msg)

    # Exposed public method to print colorted text
    def print_colored_text(self, text: str, hex_color: str):
        self._print_colored_text(text, hex_color)

    # Print info messages with specific color
    def _info(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        self._print_colored_text(msg_detail, self.hex_color_dict["info"])

        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    def _success(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] SUCCESS - {filename}: {line_number}"
        self.print_colored_text(msg_detail, self.hex_color_dict["success"])

        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    
    # Print error messages with specific color
    def _error(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] ERROR - {filename}: {line_number}"
        self._print_colored_text(msg_detail, self.hex_color_dict["error"])

        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    # Print warning messages with specific color
    def _warning(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] WARNING - {filename}: {line_number}"
        self._print_colored_text(msg_detail, self.hex_color_dict["warning"])

        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    # Print testing output with specific color
    def _testing(self, msg: str) -> None:
        # Get the current time
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Get the caller's frame to identify file and line number
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        
        # Log message details
        msg_detail = f"[{current_time}] TESTING OUTPUT - {filename}: {line_number}"
        self._print_colored_text(msg_detail, self.hex_color_dict["testing"])

        # Log message content
        self._print_colored_text(msg, self.hex_color_dict["content"])

    def _hex_to_rgb(self, hex_color: str):
        """
        Convert a hex color code to an RGB tuple.

        Args:
            hex_color (str): The hex color string (e.g., "#e6194b").

        Returns:
            tuple: An (r, g, b) tuple with RGB values.
        """
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    

    def _print_colored_text(self, text: str, hex_color: str):
        """
        Print text with a specific hex color in the terminal.

        Args:
            text (str): The text to print.
            hex_color (str): The hex color code (e.g., "#e6194b").
        """
        # Convert hex color to RGB
        r, g, b = self._hex_to_rgb(hex_color)

        # ANSI escape code for 24-bit RGB colors
        ansi_code = f"\033[38;2;{r};{g};{b}m"

        # Reset color after text
        reset_code = "\033[0m"

        # Print the colored text
        print(f"{ansi_code}{text}{reset_code}")
        
        # Auto-write logs
        self._auto_write(text)
    
    def info_with_yellow_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        # Set background color using ANSI escape codes
        r, g, b = self._hex_to_rgb(self.hex_color_dict["yellow_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        # Print with colored background
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        # Auto-write logs
        self._auto_write(msg_detail)

    def info_with_pink_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["pink_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_cyan_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["cyan_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_green_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["green_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)

    def info_with_blue_background(self, msg: str) -> None:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        frame = inspect.currentframe().f_back.f_back
        filename = os.path.basename(frame.f_code.co_filename)
        line_number = frame.f_lineno
        msg_detail = f"[{current_time}] INFO - {filename}: {line_number}"
        
        r, g, b = self._hex_to_rgb(self.hex_color_dict["blue_light"])
        bg_code = f"\033[48;2;{r};{g};{b}m"
        reset_code = "\033[0m"
        
        print(f"{bg_code}{msg_detail}{reset_code}")
        print(f"{bg_code}{msg}{reset_code}")
        
        self._auto_write(msg_detail)
        

# Logger
logger = Logger()
