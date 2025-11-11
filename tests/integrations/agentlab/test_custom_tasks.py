"""
Tests for Custom Task Support

Tests CustomWebTask class and task creation functions.
"""

import pytest

try:
    from sygra.integrations.agentlab.tasks.custom_tasks import (
        CustomWebTask,
        create_custom_task,
        create_custom_tasks,
        create_ecommerce_task,
        create_form_filling_task,
        create_search_task,
        create_web_navigation_task,
    )

    AGENTLAB_AVAILABLE = True
except ImportError:
    AGENTLAB_AVAILABLE = False


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestCustomWebTask:
    """Test CustomWebTask class"""

    def test_initialization(self):
        """Test basic task initialization"""
        task = CustomWebTask(goal="Test goal", url="https://example.com", task_id="test_001")

        assert task.goal == "Test goal"
        assert task.url == "https://example.com"
        assert task.task_id == "test_001"
        assert task.metadata is None

    def test_initialization_with_metadata(self):
        """Test initialization with metadata"""
        metadata = {"category": "testing", "priority": "high"}
        task = CustomWebTask(
            goal="Test goal", url="https://example.com", task_id="test_001", metadata=metadata
        )

        assert task.metadata == metadata

    def test_to_dict(self):
        """Test converting task to dictionary"""
        task = CustomWebTask(goal="Test goal", url="https://example.com", task_id="test_001")

        result = task.to_dict()

        assert isinstance(result, dict)
        assert result["goal"] == "Test goal"
        assert result["url"] == "https://example.com"
        assert result["task_name"] == "custom.test_001"
        assert result["task_type"] == "custom"
        assert result["id"] == "test_001"
        assert "metadata" in result

    def test_to_dict_without_task_id(self):
        """Test converting task to dict without task_id"""
        task = CustomWebTask(goal="Test goal", url="https://example.com")

        result = task.to_dict()

        assert result["task_name"] == "custom.task"
        assert result["id"].startswith("custom_")  # Hash-based ID

    def test_to_dict_with_metadata(self):
        """Test converting task with metadata to dict"""
        metadata = {"category": "testing"}
        task = CustomWebTask(goal="Test goal", url="https://example.com", metadata=metadata)

        result = task.to_dict()

        assert result["metadata"] == metadata

    def test_equality(self):
        """Test task equality comparison"""
        task1 = CustomWebTask(goal="Test goal", url="https://example.com", task_id="test_001")

        task2 = CustomWebTask(goal="Test goal", url="https://example.com", task_id="test_001")

        task3 = CustomWebTask(goal="Different goal", url="https://example.com", task_id="test_001")

        assert task1 == task2
        assert task1 != task3

    def test_dataclass_features(self):
        """Test that CustomWebTask behaves like a dataclass"""
        task = CustomWebTask(goal="Test goal", url="https://example.com")

        # Should have string representation
        assert "CustomWebTask" in str(task)
        assert "Test goal" in str(task)
        assert "https://example.com" in str(task)


@pytest.mark.skipif(not AGENTLAB_AVAILABLE, reason="AgentLab not installed")
class TestTaskFactoryFunctions:
    """Test task factory functions"""

    def test_create_custom_task(self):
        """Test creating single custom task"""
        result = create_custom_task(goal="Search for Python tutorials", url="https://google.com")

        assert isinstance(result, dict)
        assert result["goal"] == "Search for Python tutorials"
        assert result["url"] == "https://google.com"
        assert result["task_type"] == "custom"

    def test_create_custom_task_with_id(self):
        """Test creating task with custom ID"""
        result = create_custom_task(goal="Test goal", url="https://example.com", task_id="my_task")

        assert result["id"] == "my_task"
        assert result["task_name"] == "custom.my_task"

    def test_create_custom_task_with_metadata(self):
        """Test creating task with metadata"""
        result = create_custom_task(
            goal="Test goal", url="https://example.com", category="testing", priority="high"
        )

        assert result["metadata"]["category"] == "testing"
        assert result["metadata"]["priority"] == "high"

    def test_create_custom_tasks_multiple(self):
        """Test creating multiple custom tasks"""
        tasks_data = [
            {"goal": "Search for Python", "url": "https://google.com"},
            {"goal": "Find JavaScript courses", "url": "https://udemy.com"},
            {"goal": "Look up React docs", "url": "https://react.dev"},
        ]

        results = create_custom_tasks(tasks_data)

        assert len(results) == 3
        assert all(isinstance(task, dict) for task in results)
        assert all(task["task_type"] == "custom" for task in results)

    def test_create_custom_tasks_empty_list(self):
        """Test creating tasks from empty list"""
        results = create_custom_tasks([])

        assert results == []

    def test_create_web_navigation_task(self):
        """Test creating web navigation task"""
        result = create_web_navigation_task(
            start_url="https://example.com", goal="Navigate to about page"
        )

        assert isinstance(result, dict)
        assert result["url"] == "https://example.com"
        assert "Navigate to about page" in result["goal"]
        assert result["task_type"] == "custom"

    def test_create_web_navigation_task_with_actions(self):
        """Test creating navigation task with expected actions"""
        result = create_web_navigation_task(
            start_url="https://example.com",
            goal="Navigate to contact",
            expected_actions=["click", "scroll"],
        )

        assert result["metadata"]["expected_actions"] == ["click", "scroll"]

    def test_create_form_filling_task(self):
        """Test creating form filling task"""
        form_data = {"name": "John Doe", "email": "john@example.com"}

        result = create_form_filling_task(
            url="https://example.com/form", goal="Fill contact form", form_data=form_data
        )

        assert result["url"] == "https://example.com/form"
        assert result["metadata"]["form_data"] == form_data
        assert "Fill contact form" in result["goal"]

    def test_create_search_task(self):
        """Test creating search task"""
        result = create_search_task(
            search_engine_url="https://google.com", query="Python programming"
        )

        assert result["url"] == "https://google.com"
        assert "Search for: Python programming" in result["goal"]
        assert result["metadata"]["query"] == "Python programming"

    def test_create_search_task_with_expected_results(self):
        """Test creating search task with expected results count"""
        result = create_search_task(
            search_engine_url="https://google.com", query="Python programming", expected_results=10
        )

        assert result["metadata"]["expected_results"] == 10

    def test_create_ecommerce_task_buy(self):
        """Test creating e-commerce buy task"""
        result = create_ecommerce_task(
            site_url="https://shop.example.com", action="buy", product="running shoes"
        )

        assert result["url"] == "https://shop.example.com"
        assert "Buy" in result["goal"] and "running shoes" in result["goal"]
        assert result["metadata"]["action"] == "buy"
        assert result["metadata"]["product"] == "running shoes"

    def test_create_ecommerce_task_add_to_cart(self):
        """Test creating e-commerce add to cart task"""
        result = create_ecommerce_task(
            site_url="https://shop.example.com", action="add_to_cart", product="laptop"
        )

        assert "Add To Cart" in result["goal"] and "laptop" in result["goal"]
        assert result["metadata"]["action"] == "add_to_cart"

    def test_create_ecommerce_task_browse(self):
        """Test creating e-commerce browse task"""
        result = create_ecommerce_task(site_url="https://shop.example.com", action="browse")

        assert "Browse" in result["goal"]
        assert result["metadata"]["action"] == "browse"

    def test_create_ecommerce_task_custom_action(self):
        """Test creating e-commerce task with custom action"""
        result = create_ecommerce_task(site_url="https://shop.example.com", action="custom_action")

        assert "Custom Action" in result["goal"]
        assert result["metadata"]["action"] == "custom_action"

    def test_task_serialization_roundtrip(self):
        """Test that tasks can be created and converted properly"""
        # Create using factory function
        task_dict = create_custom_task(
            goal="Test goal", url="https://example.com", task_id="test_001"
        )

        # Should be a proper dictionary format
        assert isinstance(task_dict, dict)
        assert all(key in task_dict for key in ["goal", "url", "task_name", "task_type", "id"])

    def test_factory_functions_return_consistent_format(self):
        """Test that all factory functions return consistent dictionary format"""
        functions_and_args = [
            (create_web_navigation_task, {"start_url": "https://example.com", "goal": "Navigate"}),
            (
                create_form_filling_task,
                {"url": "https://example.com", "goal": "Fill form", "form_data": {}},
            ),
            (create_search_task, {"search_engine_url": "https://google.com", "query": "test"}),
            (create_ecommerce_task, {"site_url": "https://shop.com", "action": "browse"}),
        ]

        for func, args in functions_and_args:
            result = func(**args)

            # All should return dict with consistent structure
            assert isinstance(result, dict)
            assert "goal" in result
            assert "url" in result
            assert "task_type" in result
            assert result["task_type"] == "custom"

    def test_task_id_generation(self):
        """Test automatic task ID generation"""
        result1 = create_custom_task(goal="Same goal", url="https://example.com")
        result2 = create_custom_task(goal="Same goal", url="https://example.com")

        # Should generate consistent IDs for same content
        assert result1["id"] == result2["id"]

        result3 = create_custom_task(goal="Different goal", url="https://example.com")

        # Should generate different ID for different content
        assert result1["id"] != result3["id"]

    def test_metadata_handling(self):
        """Test metadata handling across factory functions"""
        result = create_web_navigation_task(
            start_url="https://example.com", goal="Navigate", custom_field="custom_value"
        )

        assert "custom_field" in result["metadata"]
        assert result["metadata"]["custom_field"] == "custom_value"
