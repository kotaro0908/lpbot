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
if __name__ == "__main__":
    # 例: 現在のtickを手動で入力
    current_tick = int(input("現場tick値を入力してください: "))
    lower_tick, upper_tick = load_range_config()
    print(f"lower_tick: {lower_tick}, upper_tick: {upper_tick}")
    if is_out_of_range(current_tick, lower_tick, upper_tick):
        print(f"❌ tick {current_tick} はレンジ外です！")
    else:
        print(f"✅ tick {current_tick} はレンジ内です。")
