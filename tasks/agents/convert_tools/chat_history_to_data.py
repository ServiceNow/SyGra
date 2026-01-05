import argparse
import json
import os
from datetime import datetime

from tasks.agents.web_agent_eval.constants import SCROLL_THRESHOLD

parser = argparse.ArgumentParser(description="Static data points collator.")
parser.add_argument("-t", "--task", type=str, default="agents/web_agent_eval", help="task name.", required=False)
args = parser.parse_args()

current_path = os.path.abspath(os.getcwd())
parent_path = "/".join(current_path.split("/")[:-2])
file = f"{parent_path}/{args.task}/static_data_points_collated.json"
write_file = f"{parent_path}/{args.task}/chat_history_seed_claude.json"

with open(file, "r") as f:
    dataf = json.load(f)
print(len(dataf))

# keep tool result images in chat history, its part of user message
# screenshot in last user message is preserved in any case for the current context
# If set it to True, update chat_history_window_size:19 in graph_config.yaml
# also sync the variable in convert_tools.py
keep_tool_result_screenshot = False

user_event_text = """Page Details: Page content does not exists above the viewport. You cannot scroll up. Page content does not exists below the viewport. You cannot scroll below. Page content does not exists to the left of the viewport. You cannot scroll left Page content does not exists to the right of the viewport. You cannot scroll right\n\n If you repeat a similar action on a specific element multiple times but it is not leading to any progress in the screenshot and you do not have any alternative to move further, then you may stop further attempts and instead use the designated tool to ask the user to manually perform that specific part of the mission. Do not keep trying forever. After the user completes it, you will resume the rest of the mission. This is an exceptional fallback, to be used only after repeated, unsuccessful efforts and you have exhausted all the alternatives. Never fallback to user preemptively or prematurely."""
user_text_midway = "You are now midway through the assigned mission. Recommend the optimal next step to drive it toward completion. Always provide a tool call in your response with the correct tool and parameters values. Follow all system prompt rules and ALWAYS prioritize the user's requirements."
user_text_start = "Help me now to complete the assigned mission. Recommend the optimal next step to drive it toward completion. Always provide a tool call in your response with the correct tool and parameters values. Follow all system prompt rules and ALWAYS prioritize the user's requirements."
if keep_tool_result_screenshot:
    chat_history_limitation = "The chat history only contains last 19 steps because of the limitation. Assuming previous steps are correct, recommend next optimal step."
    user_text_midway = user_text_midway + " " + chat_history_limitation


def extract_tool_use(record, key_tool_use):
    str_tools_use = str(record[key_tool_use]).replace("'", "\"").replace("True", "true").replace("False", "false")
    try:
        ss_tool_use = json.loads(str_tools_use)
    except:
        print("Error parsing tool use...incomplete data.")
        ss_tool_use = {}
    return ss_tool_use


def extract_tooluse_id(content_list):
    for content in content_list:
        key = list(content.keys())[0]
        if key == "toolUse":
            return content["toolUse"]["toolUseId"]
    return ""


def build_chat_history(df, iter):
    chat_history = []
    print(f"building chat for record {iter}")
    previous_event_tool_result = {}
    for i in range(iter):
        print(f"building chat for record {iter} from record {i}")
        record = df[i]
        ss_tool_use = extract_tool_use(record, "screenshot_tool_use")
        ss_tool_result = extract_tool_use(record, 'screenshot_tool_result')
        event_tool_use = extract_tool_use(record, 'event_tool_use')

        if i == 0:
            # USER - goal
            chat_history.append({"role": "user", "content": [{"type": "text", "text": user_text_start}]})
        else:
            # USER - midway goal with previous event result
            chat_history.append(
                {"role": "user", "content": [previous_event_tool_result, {"type": "text", "text": user_text_midway}]})

        # ASSISTANT - screenshot tool call
        chat_history.append(ss_tool_use)
        # USER - tool result screenshot
        ss_tool_result["content"].append({"type": "text", "text": user_text_midway})
        chat_history.append(ss_tool_result)
        # ASSISTANT - event tool call
        chat_history.append(event_tool_use)

        previous_event_tool_result = extract_tool_use(record, 'event_tool_result')

    return chat_history, previous_event_tool_result


def update_user_text(chat_history):
    first_user_msg = True
    for message in chat_history:
        if message["role"] == "user":
            text_present = False
            for content in message["content"]:
                if "text" in content.keys():
                    text_present = True
                    if first_user_msg:
                        content["text"] = user_text_start
                        first_user_msg = False
                    else:
                        content["text"] = user_text_midway
            if not text_present:
                message["content"].append({"text": user_text_midway})
    return chat_history


def get_scroll_direction(scroll_coordinates):
    """
    Determine scroll direction from scroll coordinates

    Args:
        scroll_coordinates: Dict with scrollXStart, scrollYStart, scrollXEnd, scrollYEnd

    Returns:
        str: One of "up", "down", "left", "right"
    """
    if not scroll_coordinates or not isinstance(scroll_coordinates, dict):
        return ""

    x_start = scroll_coordinates.get('scrollXStart', 0)
    y_start = scroll_coordinates.get('scrollYStart', 0)
    x_end = scroll_coordinates.get('scrollXEnd', 0)
    y_end = scroll_coordinates.get('scrollYEnd', 0)

    # Calculate the change in X and Y coordinates
    delta_x = x_end - x_start
    delta_y = y_end - y_start

    # Use threshold to determine significant movement (avoid noise)
    threshold = SCROLL_THRESHOLD  # pixels

    # Determine primary direction based on larger absolute change
    if abs(delta_x) > abs(delta_y):
        # Horizontal movement is dominant
        if delta_x > threshold:
            return "right"
        elif delta_x < -threshold:
            return "left"
    else:
        # Vertical movement is dominant
        if delta_y > threshold:
            return "down"
        elif delta_y < -threshold:
            return "up"

    # Default to down if movement is minimal (most scrolls are down)
    return "down"


rows = len(dataf)
test_records = []
prev_scenario_id = dataf[0]["scenario_id"]
empty_chat_history_count = 0  # Counter for empty/None chat_history cases

# Add typedValue into data rows for further usage
for i in range(rows):
    if dataf[i].get("selectors") is not None and dataf[i].get("selectors").get("meta") is not None:
        dataf[i].update({"typedValue": dataf[i]["selectors"]["meta"].get("typedValue")})
    else:
        dataf[i].update({"typedValue": None})

for r in range(rows):
    mission_id = "mission_0" + str(dataf[r]["scenario_id"])
    navigational_direction = ""
    current_scneario_id = dataf[r]["scenario_id"]
    # screenshot_base64 = dataf[r]["screenshot_after"]
    turn = dataf[r]["step_id"]
    prev_scenario_id = current_scneario_id
    rec_id = mission_id + str("_") + str(turn)
    mission = dataf[r]["objective"]
    chat_history = dataf[r]["chat_history"]

    # JSON Loads chat history - handle None/empty cases (first record of each mission)
    try:
        if chat_history is None or chat_history == "" or chat_history == "null":
            raise ValueError("Empty chat_history")
        modified_chat_history = json.loads(chat_history)
        print(f"Length of chat history is {len(modified_chat_history)}")
        # -2 is result and -1 is event tool result which we don't need
        current_node = modified_chat_history[-3]
        current_tool_use = current_node["content"][0]
        modified_chat_history = modified_chat_history[:-3]
        modified_chat_history = update_user_text(modified_chat_history)
    except (ValueError, json.JSONDecodeError, IndexError, TypeError) as e:
        print(f"Skipping record {r} (mission_id: {mission_id}) - Empty/invalid chat_history: {e}")
        empty_chat_history_count += 1
        continue
    current_user_text = user_text_midway
    golden_event = dataf[r]["event_type"]
    golden_event_prop = extract_tool_use(dataf[r], "bbox")
    if golden_event == "typing":
        if r >= 1:
            golden_event_prop["text"] = dataf[r].get("typedValue", "")
            val = golden_event_prop["text"]
            print(f"The identified typed text is {val}")
    if golden_event == "scroll":
        # Extract scroll coordinates from the dataset record
        scroll_coordinates = dataf[r].get("scroll_coordinates", {})
        scroll_direction = get_scroll_direction(scroll_coordinates)
        if scroll_direction:
            golden_event_prop["direction"] = scroll_direction
            print(f"Extracted scroll direction: {scroll_direction} from coordinates: {scroll_coordinates}")
        else:
            print(f"Warning: Could not determine scroll direction from coordinates: {scroll_coordinates}")

    test_records.append({"id": rec_id,
                         "mission_id": mission_id,
                         "mission": mission,
                         "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         "navigational_directions": navigational_direction,
                         "turn": turn,
                         # "screenshot": screenshot_base64,
                         "chat_history": modified_chat_history,
                         "current_user_text": current_user_text,
                         "current_tool_result": current_tool_use,
                         "golden_response": {
                             "event": golden_event,
                             "properties": golden_event_prop
                         }
                         })

with open(write_file, "w") as f:
    json.dump(test_records, f, indent=4)

print(f"\n=== PROCESSING SUMMARY ===")
print(f"Total records processed: {len(test_records)}")
print(f"Records with empty/invalid chat_history: {empty_chat_history_count}")
print(f"These should correspond to the first record of each distinct mission.")

# Calculate number of distinct missions for verification
distinct_missions = len(set(dataf[r]["scenario_id"] for r in range(rows)))
print(f"Number of distinct missions (scenarios): {distinct_missions}")
if empty_chat_history_count == distinct_missions:
    print("✓ SUCCESS: Empty chat_history count matches number of distinct missions!")
else:
    print(
        f"⚠️  WARNING: Empty chat_history count ({empty_chat_history_count}) does not match distinct missions ({distinct_missions})")
    print("This may indicate faulty records that need investigation.")