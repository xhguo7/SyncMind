"""
JSON Utils
"""

import os
import json

def save_to_json(data: dict, file_path: str) -> None:
    """
    Saves the given dictionary data to a JSON file at the specified file path.

    :param data: Dictionary data to be saved.
    :param file_path: The path where the JSON file will be saved.
    """
    with open(file_path, 'w', encoding='utf-8') as json_file:
        json.dump(data, json_file, indent=4)


def read_json_data(file_path: str) -> dict:
    """
    Reads JSON data from a file and returns it as a dictionary.
    If the file does not exist or is empty, returns an empty dictionary.

    :param file_path: The path of the JSON file to be read.
    :return: Dictionary containing the JSON data or an empty dictionary if the file does not exist or is empty.
    """
    if os.path.exists(file_path):
        if os.path.getsize(file_path) > 0:
            with open(file_path, 'r', encoding='utf-8') as json_file:
                data = json.load(json_file)
            return data
        else:
            return {}
    else:
        return {}
    