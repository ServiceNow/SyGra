"""
Error Detection Utilities for Web Agent Evaluation

This module provides utilities to detect different types of errors in model responses:
1. Server errors - Infrastructure/API issues (e.g., timeouts, service unavailable)
2. Structural errors - Data/format issues (e.g., malformed tool calls, missing required fields)

Server errors can potentially be resolved in subsequent retries, while structural errors
indicate data quality issues that need to be addressed separately.
"""

from typing import List, Dict, Any
from sygra.logger.logger_config import logger
from tasks.agents.web_agent_eval.constants import SERVER_DOWN_ERROR


class StructuralError(Exception):
    """
    Exception raised when a structural error is detected in model response.
    Structural errors indicate data quality issues that should be handled separately
    from valid failures and server errors.
    """
    pass


def is_server_error(response_text: str, tool_calls: List[Dict[str, Any]]) -> bool:
    """
    Detect if the response contains a server/infrastructure error.
    Server errors are transient issues that might be resolved in subsequent retries.
    
    Examples:
    - API timeouts
    - Service unavailable
    - Throttling exceptions
    - Internal server errors
    
    Args:
        response_text: Model's text response
        tool_calls: Model's tool calls
        
    Returns:
        bool: True if this is a server error, False otherwise
    """
    # Check for server error markers in response text
    server_error_markers = [
        SERVER_DOWN_ERROR
    ]
    
    response_lower = response_text.lower() if response_text else ""
    for marker in server_error_markers:
        if marker.lower() in response_lower:
            logger.warning(f"Server error detected: {marker}")
            return True
    
    return False


def is_structural_error(response_text: str, tool_calls: List[Dict[str, Any]]) -> bool:
    """
    Detect if the response has structural/data quality issues.
    Structural errors indicate problems with data format or validation that need
    to be addressed separately from valid failures.
    
    Examples:
    - Validation errors (constraint violations)
    - Empty responses (no text and no tool calls)
    - Malformed tool calls (missing name, invalid structure)
    - Schema validation failures
    
    Args:
        response_text: Model's text response
        tool_calls: Model's tool calls
        
    Returns:
        bool: True if this is a structural error, False otherwise
    """
    # Check for validation/constraint error markers
    structural_error_markers = [
        "validation errors detected",
        "failed to satisfy constraint",
        "Member must satisfy regular expression",
        "Member must have length",
        "ValidationException",
        "InvalidParameterException",
        "SchemaValidationException"
    ]
    
    response_lower = response_text.lower() if response_text else ""
    for marker in structural_error_markers:
        if marker.lower() in response_lower:
            logger.warning(f"Structural error detected: {marker}")
            return True
    
    # Check if response is partially/completely empty (Either no response text or no tool calls)
    if not response_text or not tool_calls:
        logger.warning("Structural error detected: Empty response (no text or no tool calls)")
        return True
    
    # Check if tool_calls have structural issues
    if tool_calls:
        for i, tool_call in enumerate(tool_calls):
            if not isinstance(tool_call, dict):
                logger.warning(f"Structural error detected: Tool call {i} is not a dict: {type(tool_call)}")
                return True
            
            func = tool_call.get('function', {})
            if not isinstance(func, dict):
                logger.warning(f"Structural error detected: Tool call {i} function is not a dict: {type(func)}")
                return True
            
            name = func.get('name', '')
            # Empty or invalid tool name indicates structural error
            if not name or name.strip() == '':
                logger.warning(f"Structural error detected: Tool call {i} has empty or invalid name")
                return True
    
    return False


def check_response_errors(response_text: str, tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Comprehensive error check that categorizes the response.
    
    This function checks for both server and structural errors and returns
    a detailed result indicating the error type (if any).
    
    Args:
        response_text: Model's text response
        tool_calls: Model's tool calls
        
    Returns:
        dict: {
            'has_error': bool,
            'error_type': str,  # 'server', 'structural', or None
            'is_valid_attempt': bool  # True if this is a valid attempt (no errors)
        }
    
    Raises:
        StructuralError: If a structural error is detected (when raise_on_structural=True)
    """
    # Check for server errors first
    if is_server_error(response_text, tool_calls):
        return {
            'has_error': True,
            'error_type': 'server',
            'is_valid_attempt': False
        }
    
    # Check for structural errors
    if is_structural_error(response_text, tool_calls):
        return {
            'has_error': True,
            'error_type': 'structural',
            'is_valid_attempt': False
        }
    
    # No errors detected - this is a valid attempt
    return {
        'has_error': False,
        'error_type': None,
        'is_valid_attempt': True
    }


def raise_if_structural_error(response_text: str, tool_calls: List[Dict[str, Any]]) -> None:
    """
    Check for structural errors and raise StructuralError exception if found.
    
    This is useful when you want to handle structural errors separately
    (e.g., skip them from metrics calculation).
    
    Args:
        response_text: Model's text response
        tool_calls: Model's tool calls
        
    Raises:
        StructuralError: If a structural error is detected
    """
    if is_structural_error(response_text, tool_calls):
        error_msg = f"Structural error detected in response. Text: '{response_text[:100]}...', Tool calls: {len(tool_calls) if tool_calls else 0}"
        raise StructuralError(error_msg)
