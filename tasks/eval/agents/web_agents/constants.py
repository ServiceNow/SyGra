# Server error detection
SERVER_DOWN_ERROR = "###SERVER_ERROR###"
SERVER_ERROR_MARKERS = [SERVER_DOWN_ERROR]

# Tool configuration
TOOL_NAME_SUFFIX = "_tool"
TOOL_NAME_MAPPINGS = {
    "type": "typing",
    "typing": "typing",
    "text_clear": "clear-typing",
    "hil": "HIL",
    "wait": "waiting",
    "slider": "slider-drag"
}

# Tool type constants
TOOL_TYPE_CLICK = "click"
TOOL_TYPE_TYPING = "typing"
TOOL_TYPE_SCROLL = "scroll"

# Property keys
PROPERTY_KEY_TOOL = "tool"

# Retry configuration
DEFAULT_MAX_RETRIES = 3
RETRY_KEY_PREFIX = "retry_"

# Image scale factors
IMAGE_SCALE_FACTORS = {
    "50_percent": 0.5,
    "25_percent": 0.25,
    "30_percent": 0.3
}

# Logging configuration
LOG_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
LOG_FILE_PREFIX = "web_agent_requests_"

# State keys
CHAT_HISTORY_STATE_KEY = "__chat_history__"
CHAT_HISTORY_BASE_KEY = "chat_history"
MODEL_RESPONSES_KEY = "model_responses"
GOLDEN_RESPONSE_KEY = "golden_response"
CURRENT_TOOL_RESULT_KEY = "current_tool_result"
CURRENT_USER_TEXT_KEY = "current_user_text"
ORIGINAL_USER_TEXT_KEY = "original_current_user_text"
CURRENT_SCREENSHOT_KEY = "current_screenshot"

# Retry injection configuration
RETRY_CONFIG_KEY = "retry_chat_injection"
RETRY_CONFIG_REQUIRED = "required"
RETRY_CONFIG_PROMPT_INJECTION = "retry_prompt_injection"

# Configuration values
CONFIG_VALUE_YES = "yes"
CONFIG_VALUE_NO = "no"

# Chat roles
CHAT_ROLE_USER = "user"
CHAT_ROLE_ASSISTANT = "assistant"
CHAT_ROLE_TOOL = "tool"

# Content types
CONTENT_TYPE_IMAGE = "image_url"
CONTENT_TYPE_TEXT = "text"

# Messages
TOOL_EXECUTION_MESSAGE = "Tool execution completed"
NO_TEXT_RESPONSE_PLACEHOLDER = "[No text response]"

# Failure hints
FAILURE_HINT_TOOL_INCORRECT = "Your previous tool call '{predicted_tool}' was incorrect. Do NOT use this tool again in the retry, even with different arguments. \nIf you believe the previous tool might still be right, dismiss that belief and proceed with a different tool call."
FAILURE_HINT_PARAMS_INCORRECT = "Your previous tool call '{predicted_tool}' was correct, but had incorrect parameters. Use the same tool again but give the correct parameters in this retry."
FAILURE_HINT_RETRY_TEMPLATE = "{failure_hint} You are now retrying this step (Retry {retry_number}). Always provide a tool call in your response with the correct tool and parameters values. The latest screenshot provided is before executing your previous wrong response. So, you can directly suggest the new different correct approach on the given screenshot without considering any cleanup tool. Ensure your response progresses towards mission completion. Follow all system prompt rules and ALWAYS prioritize the user's requirements."