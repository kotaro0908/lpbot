import json

def load_range_config(path="range_config.json"):
    with open(path, "r") as f:
        data = json.load(f)
    return data["lower_tick"], data["upper_tick"]

def is_out_of_range(current_tick, lower_tick, upper_tick):
    return current_tick < lower_tick or current_tick > upper_tick

def check_range(current_tick):
    lower_tick, upper_tick = load_range_config()
    return is_out_of_range(current_tick, lower_tick, upper_tick)
