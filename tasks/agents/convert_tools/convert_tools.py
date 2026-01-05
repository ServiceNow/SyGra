
import argparse
import json
import os

parser = argparse.ArgumentParser(description="Static data points collator.")
parser.add_argument("-t", "--task", type=str, default="agents/web_agent_eval", help="task name.", required=False)
args = parser.parse_args()

current_path = os.path.abspath(os.getcwd())
parent_path = "/".join(current_path.split("/")[:-2])
seed_file = f"{parent_path}/{args.task}/chat_history_seed_claude.json"
seed_write = f"{parent_path}/{args.task}/chat_history_seed.json"
# keep tool result images in chat history, its part of user message
# screenshot in last user message is preserved in any case for the current context
# If set it to True, update chat_history_window_size:19 in graph_config.yaml
# also sync the variable in chat_history_to_data.py
keep_tool_result_screenshot = False

with open(seed_file, "r") as f:
    seed_data = json.load(f)

for seed in seed_data:
    current_tool_name = ""
    index = 0
    #insert_tool_index = 0
    chat_history = seed.get("chat_history", [])
    # index to insert and the tool result node
    insert_tool_role = {}
    for chat in chat_history:
        index = index + 1
        if chat.get("role") == "system":
            final_content = []
            for c in chat.get("content"):
                dict_keys = list(c.keys())
                if "text" in dict_keys:
                    c["type"] = "text"
                    final_content.append(c)
                else:
                    print(f"ERROR:{str(chat)}")
            chat["content"] = final_content
        elif chat.get("role") == "assistant":
            for c in chat.get("content"):
                dict_keys = list(c.keys())
                if "text" in dict_keys:
                    chat["content"] = c.get("text")
                    del c["text"]
                elif len(dict_keys) == 1 and dict_keys[0] == "toolUse":
                    type_val = "function"
                    tool_call_id = c.get("toolUse", {}).get("toolUseId")
                    current_tool_name = c.get("toolUse", {}).get("name")
                    if c.get("toolUse", {}).get("input"):
                        function_val = {"name": current_tool_name, "arguments": json.dumps(c.get("toolUse", {}).get("input", ""))}
                    else:
                        function_val = {"name": current_tool_name}
                    chat["tool_calls"] = [{"id": tool_call_id, "type": type_val, "function": function_val}]
                    # build tool call for role:tool as next message node
                    chat_tool_result = {"role": "tool", "tool_call_id": tool_call_id, "name": current_tool_name,
                                        "content": "success"}
                    insert_tool_role[index] = chat_tool_result

                    del c["toolUse"]
                else:
                    print(f"ERROR assistant role:{str(chat)}")
        elif chat.get("role") == "user":
            final_content = []
            chat_tool_result = None
            for c in chat.get("content"):
                dict_keys = list(c.keys())
                if "text" in dict_keys:
                    c["type"] = "text"
                    final_content.append(c)
                elif len(dict_keys) == 1 and dict_keys[0] == "toolResult":
                    #tool_call_id = c.get("toolResult", {}).get("toolUseId")
                    #if current_tool_name == "":
                    #    print(f"missing tool name for tool id : {tool_call_id}")
                    if c.get("toolResult", {}).get("status") == "success" and len(c.get("toolResult", {}).get("content")) > 0:
                        # If image is present extract and pass as image data
                        content =  c.get("toolResult", {}).get("content")
                        if len(content) == 1 and content[0].get("image") and keep_tool_result_screenshot:
                            img_fmt = content[0].get("image", {}).get("format")
                            img_content = content[0].get("image", {}).get("source", {}).get(
                                "bytes")
                            # openai format image in base64
                            img_content_url = f"data:image/{img_fmt};base64,{img_content}"
                            final_content.append({"type": "image_url", "image_url": {"url": img_content_url}})
                    # extracted tool result
                    #chat_tool_result = {"role":"tool", "tool_call_id":tool_call_id, "name": current_tool_name, "content":"success"}
                    #insert_tool_index = index - 1
                    #insert_tool_role[insert_tool_index] = chat_tool_result
                else:
                    print(f"ERROR user role:{str(chat)}")
            chat["content"] = final_content
    # insert tool result before user text, as role:tool
    insert_index_adjustment = 0
    for ind, chat in insert_tool_role.items():
        chat_history.insert(ind + insert_index_adjustment, chat)
        insert_index_adjustment += 1

    seed["chat_history"] = chat_history

    # now work on current_tool_result
    current_tool_result = seed.get("current_tool_result", {})
    tool_call_id = current_tool_result.get("toolResult", {}).get("toolUseId")
    # use the last selected tool in tool_call(last assistant response in chat history)
    if current_tool_name == "":
        print(f"missing tool name for tool id : {tool_call_id}")
    if current_tool_result.get("toolResult", {}).get("status") == "success" and len(current_tool_result.get("toolResult", {}).get("content")) > 0:
        # set the content as it is
        # TODO: do we need to convert image to different format?
        content = current_tool_result.get("toolResult", {}).get("content")
    else:
        content = [{"text": "failure"}]

    # extracted tool result
    converted_tool_result = {"role": "tool", "tool_call_id": tool_call_id, "name": current_tool_name, "content": content}
    seed["current_tool_result"] = converted_tool_result

'''
# filter data for debugging
missions = ["mission_03_15","mission_03_17"]
final_seed_data= []
l = len(seed_data)
for i in range(l):
    seed = seed_data[i]
    for mission in missions:
        if mission in str(seed.get("id")):
            final_seed_data.append(seed)
            print("added ", seed.get("id"))
            break
    #print("skipping ", seed.get("id"))
seed_data = final_seed_data
'''

with open(seed_write, "w") as f:
    json.dump(seed_data, f, indent=4)
