"""Task executor for web agent demo.

Provides output generator for web automation workflows.
"""

from typing import Any

from sygra.core.graph.sygra_state import SygraState
from sygra.processors.output_record_generator import BaseOutputGenerator


class WebAgentOutputGenerator(BaseOutputGenerator):
    """Output generator for web agent results.

    This passes through all data from the state without transformation.
    """
    pass
