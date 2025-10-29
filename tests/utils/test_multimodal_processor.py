"""Tests for multimodal_processor utility functions."""

import shutil
import tempfile
from pathlib import Path

import pytest

from sygra.utils.multimodal_processor import (
    is_multimodal_data_url,
    process_batch_multimodal_data,
    process_record_multimodal_data,
    save_multimodal_data_url,
)


class TestIsMultimodalDataURL:
    """Tests for is_multimodal_data_url function."""

    def test_image_data_url(self):
        """Test that image data URLs are recognized."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        assert is_multimodal_data_url(data_url) is True

    def test_audio_data_url(self):
        """Test that audio data URLs are recognized."""
        data_url = "data:audio/mp3;base64,SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4Ljc2LjEwMAAAAAAAAAAAAAAA"
        assert is_multimodal_data_url(data_url) is True

    def test_not_data_url(self):
        """Test that regular strings are not recognized."""
        assert is_multimodal_data_url("hello world") is False
        assert is_multimodal_data_url("http://example.com") is False
        assert is_multimodal_data_url(123) is False
        assert is_multimodal_data_url(None) is False


class TestProcessBatchMultimodalData:
    """Tests for process_batch_multimodal_data function."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up temporary directory after each test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_no_multimodal_data_no_directory_created(self):
        """Test that directory is NOT created when there's no multimodal data."""
        records = [
            {"id": "1", "text": "Hello world"},
            {"id": "2", "text": "Another record"},
        ]
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory should NOT be created
        assert not output_dir.exists()
        
        # Records should be unchanged
        assert result == records

    def test_with_multimodal_data_directory_created(self):
        """Test that directory IS created when there's multimodal data."""
        # Sample 1x1 PNG as data URL
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        records = [
            {"id": "1", "image": data_url},
        ]
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory SHOULD be created
        assert output_dir.exists()
        assert output_dir.is_dir()
        
        # Image subdirectory should exist
        assert (output_dir / "image").exists()

    def test_mixed_records_directory_created(self):
        """Test that directory is created when at least one record has multimodal data."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        records = [
            {"id": "1", "text": "No image"},
            {"id": "2", "image": data_url},  # Has image
            {"id": "3", "text": "Also no image"},
        ]
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory SHOULD be created because at least one record has multimodal data
        assert output_dir.exists()

    def test_nested_multimodal_data_detected(self):
        """Test that nested multimodal data is detected."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        records = [
            {
                "id": "1",
                "nested": {
                    "deep": {
                        "image": data_url
                    }
                }
            },
        ]
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory SHOULD be created because nested data contains image
        assert output_dir.exists()

    def test_multimodal_data_in_list_detected(self):
        """Test that multimodal data in lists is detected."""
        data_url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        
        records = [
            {
                "id": "1",
                "images": [data_url, "text", "more text"]
            },
        ]
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory SHOULD be created because list contains image
        assert output_dir.exists()

    def test_empty_records_no_directory(self):
        """Test that empty records list doesn't create directory."""
        records = []
        
        output_dir = self.temp_dir / "multimodal_output"
        
        # Process records
        result = process_batch_multimodal_data(records, output_dir)
        
        # Directory should NOT be created
        assert not output_dir.exists()
        
        # Result should be empty list
        assert result == []
