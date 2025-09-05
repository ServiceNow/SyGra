# Structured Output

This example demonstrates how to implement structured output from LLM responses within the GraSP framework. It showcases how to extract specific information from LLM responses in a standardized JSON format using structured output that can be reliably parsed and processed in downstream applications.

> **Key Features**:
> `structured JSON output`, `schema definition`, `post-processing`, `code taxonomy`, `response normalization`

## Overview

The Structured Output example is designed to:

- **Extract structured data**: Automatically respond in a well-defined schema for easy parsing and processing

## Directory Contents

- `task_executor.py`: Core functionality for processing and extracting structured data from LLM responses
- `graph_config.yaml`: Configuration file defining the workflow graph and structured output schema

## How It Works

1. **Data Source**:
   - The system loads code snippets from the "glaiveai/glaive-code-assistant-v2" HuggingFace dataset
   - Each entry contains a programming question that includes code

2. **Schema Definition**:
   - The `structured_output` section in the model configuration defines a schema with:
     - `category`: String field for the main category of the code snippet
     - `sub_category`: String field for a more specific categorization

3. **LLM Processing**:
   - The `generate_taxonomy` node sends the code snippet to the LLM
   - The LLM identifies the appropriate category and subcategory based on the code content
   - The response is formatted according to the defined schema

4. **Post-Processing**:
   - The `GenerateTaxonomyPostProcessor` extracts the structured data from the LLM response
   - It handles potential JSON parsing errors through regex fallbacks
   - The extracted data is added to the state for downstream use

5. **Output Formatting**:
   - The system formats the final output with:
     - Original question ID and content
     - Extracted category and subcategory information