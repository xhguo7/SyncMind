"""
Util functions for json
"""

import json

# Save to json
def save_to_json(data, save_path):
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# Read json
def read_test_data(test_data_path):
    # Open and read the JSON file
    with open(test_data_path, 'r', encoding='utf-8') as file:
        test_dict = json.load(file)
    return test_dict

# Read Generated test data & Cache test data
def read_generated_cache_data(args, repo_id, repo_name):
    # (1) Read Generated test data
    # Define the path to the JSON file
    generated_data_path = f"{args.root_path}{args.repo_path}{repo_id}_{repo_name}_generate.json"
    # Open and read the JSON file
    with open(generated_data_path, 'r') as file:
        generated_data = json.load(file)

    # (2) Read Cache test data
    # Define the path to the JSON file
    cache_data_path = f"{args.root_path}{args.repo_path}{repo_id}_{repo_name}_cache.json"
    # Open and read the JSON file
    with open(cache_data_path, 'r') as file:
        cache_data = json.load(file)

    return generated_data, cache_data

# Read generated test data
def read_generated_test_data(args, repo_id, repo_name):
    # (1) Read Generated test data
    # Define the path to the JSON file
    generated_data_path = f"{args.root_path}{args.repo_path}{repo_id}_{repo_name}_generate.json"
    # Open and read the JSON file
    with open(generated_data_path, 'r') as file:
        generated_data = json.load(file)
    return generated_data
