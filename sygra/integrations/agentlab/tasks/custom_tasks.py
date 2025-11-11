"""
Custom Task Support for Web Agents

This module provides support for open-ended custom tasks on any website,
in addition to benchmark tasks from AgentLab.
"""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class CustomWebTask:
    """
    Represents a custom web task with a goal and target URL.

    Attributes:
        goal: Natural language description of the task
        url: Starting URL for the task
        task_id: Optional unique identifier
        metadata: Optional additional metadata

    Example:
        >>> task = CustomWebTask(
        ...     goal="Book a ticket for 2 people from SFO to JFK for tomorrow",
        ...     url="https://www.makemytrip.com",
        ...     task_id="booking_001"
        ... )
    """

    goal: str
    url: str
    task_id: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for SyGra workflow."""
        return {
            "task_name": f"custom.{self.task_id}" if self.task_id else "custom.task",
            "goal": self.goal,
            "url": self.url,
            "task_type": "custom",
            "metadata": self.metadata or {},
            "id": self.task_id or f"custom_{hash(self.goal + self.url)}",
        }


def create_custom_task(
    goal: str, url: str, task_id: Optional[str] = None, **metadata
) -> dict[str, Any]:
    """
    Create a custom web task.

    Args:
        goal: Natural language description of what to accomplish
        url: Starting URL (e.g., "https://www.makemytrip.com")
        task_id: Optional unique identifier for the task
        **metadata: Additional metadata to store with the task

    Returns:
        dict: Task dictionary ready for SyGra workflow

    Example:
        >>> task = create_custom_task(
        ...     goal="Book a ticket for 2 people from SFO to JFK for tomorrow",
        ...     url="https://www.makemytrip.com",
        ...     task_id="booking_001",
        ...     passengers=2,
        ...     origin="SFO",
        ...     destination="JFK"
        ... )
        >>> workflow.source([task])
    """
    task = CustomWebTask(
        goal=goal, url=url, task_id=task_id, metadata=metadata if metadata else None
    )
    return task.to_dict()


def create_custom_tasks(tasks: list[dict[str, str]]) -> list[dict[str, Any]]:
    """
    Create multiple custom tasks from a list of goal/URL pairs.

    Args:
        tasks: list of dicts with 'goal' and 'url' keys

    Returns:
        list: list of task dictionaries

    Example:
        >>> tasks = create_custom_tasks([
        ...     {
        ...         "goal": "Search for flights from SFO to JFK",
        ...         "url": "https://www.google.com/flights"
        ...     },
        ...     {
        ...         "goal": "Find hotels in New York",
        ...         "url": "https://www.booking.com"
        ...     }
        ... ])
        >>> workflow.source(tasks)
    """
    result = []
    for i, task_dict in enumerate(tasks):
        task = create_custom_task(
            goal=task_dict["goal"],
            url=task_dict["url"],
            task_id=task_dict.get("task_id", f"task_{i+1}"),
            **{k: v for k, v in task_dict.items() if k not in ["goal", "url", "task_id"]},
        )
        result.append(task)
    return result


def create_web_navigation_task(
    start_url: str,
    goal: str,
    expected_actions: Optional[list[str]] = None,
    success_criteria: Optional[str] = None,
    **metadata,
) -> dict[str, Any]:
    """
    Create a web navigation task with optional success criteria.

    Args:
        start_url: Starting URL
        goal: Task description
        expected_actions: Optional list of expected action types
        success_criteria: Optional description of success conditions
        **metadata: Additional metadata

    Returns:
        dict: Task dictionary

    Example:
        >>> task = create_web_navigation_task(
        ...     start_url="https://www.amazon.com",
        ...     goal="Search for 'wireless mouse' and add to cart",
        ...     expected_actions=["search", "click", "add_to_cart"],
        ...     success_criteria="Item added to cart successfully"
        ... )
    """
    meta = metadata.copy()
    if expected_actions:
        meta["expected_actions"] = expected_actions
    if success_criteria:
        meta["success_criteria"] = success_criteria

    return create_custom_task(goal=goal, url=start_url, **meta)


def create_form_filling_task(
    url: str, goal: str, form_data: dict[str, Any], **metadata
) -> dict[str, Any]:
    """
    Create a form filling task with data to fill.

    Args:
        url: URL of the form
        goal: Task description
        form_data: dictionary of field names and values
        **metadata: Additional metadata

    Returns:
        dict: Task dictionary

    Example:
        >>> task = create_form_filling_task(
        ...     url="https://forms.example.com/contact",
        ...     goal="Fill out contact form",
        ...     form_data={
        ...         "name": "John Doe",
        ...         "email": "john@example.com",
        ...         "message": "Hello!"
        ...     }
        ... )
    """
    meta = metadata.copy()
    meta["form_data"] = form_data
    meta["task_category"] = "form_filling"

    return create_custom_task(goal=goal, url=url, **meta)


def create_search_task(
    search_engine_url: str, query: str, expected_results: Optional[int] = None, **metadata
) -> dict[str, Any]:
    """
    Create a search task.

    Args:
        search_engine_url: URL of search engine
        query: Search query
        expected_results: Optional number of expected results
        **metadata: Additional metadata

    Returns:
        dict: Task dictionary

    Example:
        >>> task = create_search_task(
        ...     search_engine_url="https://www.google.com",
        ...     query="best restaurants in San Francisco",
        ...     expected_results=10
        ... )
    """
    meta = metadata.copy()
    meta["query"] = query
    meta["task_category"] = "search"
    if expected_results:
        meta["expected_results"] = expected_results

    return create_custom_task(goal=f"Search for: {query}", url=search_engine_url, **meta)


def create_ecommerce_task(
    site_url: str, action: str, product: Optional[str] = None, **metadata
) -> dict[str, Any]:
    """
    Create an e-commerce task (search, add to cart, checkout, etc.).

    Args:
        site_url: E-commerce site URL
        action: Action to perform (search, add_to_cart, checkout, etc.)
        product: Optional product name/description
        **metadata: Additional metadata

    Returns:
        dict: Task dictionary

    Example:
        >>> task = create_ecommerce_task(
        ...     site_url="https://www.amazon.com",
        ...     action="search_and_add_to_cart",
        ...     product="wireless mouse",
        ...     quantity=2
        ... )
    """
    meta = metadata.copy()
    meta["task_category"] = "ecommerce"
    meta["action"] = action
    if product:
        meta["product"] = product

    goal = f"{action.replace('_', ' ').title()}"
    if product:
        goal += f" for {product}"

    return create_custom_task(goal=goal, url=site_url, **meta)
