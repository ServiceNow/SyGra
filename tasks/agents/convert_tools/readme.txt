Once we recieve the data from data generation work, follow these steps:
1. run static_data_point_collator.py after changing the path(set the default_path or pass into command line argument)
2. run chat_history_to_data.py
3. run convert_tools.py. This should help converting the tools into openai format.

If you want screenshot in every tool result of the chat history set keep_tool_result_screenshot to True in convert_tools.py and chat_history_to_data.py.
Also set chat_history_window_size to 19 in graph_config.yaml, this will make sure sending max 20 images(claude limit in bedrock).

By default, the variable keep_tool_result_screenshot is False and chat_history_window_size is 1000.
It will only send screenshot/image in last user turn, to pass current context to the model.