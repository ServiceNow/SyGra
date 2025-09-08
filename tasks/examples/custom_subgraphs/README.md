# Custom Subgraphs

This example demonstrates how to create and use custom subgraphs within the GraSP framework. It showcases a modular approach to building complex AI systems by composing reusable graph components that can be developed and tested independently.

> **Key Features**:
> `custom subgraphs`, `modular design`, `code generation`, `self-critique`, `feedback loops`

## Overview

The Custom Subgraphs example is designed to:

- **Create reusable components**: Define independent graph modules that can be referenced in other graphs
- **Compose complex workflows**: Combine subgraphs with standard nodes in parent graphs
- **Demonstrate modular AI systems**: Show how to break down complex tasks into manageable components
- **Implement feedback loops**: Create iterative improvement processes across graph boundaries

## Directory Contents

- `task_executor.py`: Core functionality for orchestrating the subgraph execution and feedback loop
- `graph_config.yaml`: Configuration file defining the main workflow graph including subgraph references
- `generate_question_subgraph/`: Directory containing a subgraph implementation
  - `graph_config.yaml`: Configuration for the question generation subgraph

## How It Works

1. **Data Source**:
   - The system loads programming problems from the MBPP (Mostly Basic Python Programming) dataset
   - Each problem includes a task description and test cases for verification

2. **Question Generation Subgraph**:
   - The `generate_question` node references an external subgraph for question processing
   - The subgraph includes:
     - `persona_sampler`: Randomly selects personas and communication styles
     - `paraphrase_question`: Reformulates the original question with selected persona attributes

3. **Solution Generation**:
   - The main graph's `generate_answer` node receives the processed question
   - The LLM produces a Python code solution based on the paraphrased question
   - Code is focused and avoids unnecessary conversational text

4. **Critique Cycle**:
   - The `critique_answer` node evaluates the solution against the test cases
   - It identifies issues and provides specific recommendations for improvement
   - The feedback is used to refine the solution in subsequent iterations

5. **Iteration Loop**:
   - The system cycles between solution generation and critique nodes
   - The loop continues until either:
     - The critique responds with "NO MORE FEEDBACK" (indicating a correct solution)
     - The maximum number of iterations is reached (8 rounds)

## Usage

This example demonstrates techniques for:
- Creating modular, reusable graph components with subgraphs
- Building self-improving systems through feedback loops
- Designing flexible persona-based interaction patterns
- Processing programming problems with test-based validation

To customize this example:
- Create new subgraphs for different processing steps
- Modify the persona attributes to change interaction styles
- Adjust the critique criteria for different coding standards
- Add additional subgraphs for more complex workflows

## Example Output

```json
[
    {
        "id": 602,
        "conversation": [
            {
                "role": "user",
                "content": "Could you provide a Python function that identifies the first character that repeats in a specified string?"
            },
            {
                "role": "assistant",
                "content": "```python\ndef first_repeating_character(s):\n    seen = set()\n    for char in s:\n        if char in seen:\n            return char\n        seen.add(char)\n    return None\n\n# Example usage:\n# print(first_repeating_character(\"swiss\"))  # Output: 's'\n```"
            }
        ],
        "metadata": {
            "original_question": "Write a python function to find the first repeated character in a given string.",
            "rephrased_text": "PARAPHRASED QUESTION: Could you provide a Python function that identifies the first character that repeats in a specified string?",
            "taxonomy": [
                {
                    "category": "Coding",
                    "subcategory": ""
                }
            ],
            "annotation_type": [
                "gpt-4o"
            ],
            "language": [
                "en"
            ],
            "tags": [
                "mbpp",
                "reannotate",
                "self-critique"
            ]
        }
    },
    {
        "id": 603,
        "conversation": [
            {
                "role": "user",
                "content": "Could you provide a Python function that calculates all lucid numbers less than or equal to a specified integer?"
            },
            {
                "role": "assistant",
                "content": "```python\ndef is_lucid_number(n):\n    while n > 0:\n        digit = n % 10\n        n //= 10\n        if n > 0 and digit <= n % 10:\n            return False\n    return True\n\ndef lucid_numbers_up_to(max_num):\n    return [num for num in range(1, max_num + 1) if is_lucid_number(num)]\n\n# Example usage:\n# lucid_numbers = lucid_numbers_up_to(100)\n# print(lucid_numbers)\n```"
            },
            {
                "role": "user",
                "content": "Your current implementation is attempting to identify a property of numbers related to their digits, but the problem is requesting to find \"ludic numbers.\" Ludic numbers require a different approach, somewhat similar to the sieve of Eratosthenes used for finding prime numbers.\n\nHere's some feedback to help guide you:\n\n1. **Understand Ludic Numbers**: Ludic numbers are generated through a sieving process, removing every k-th number iteratively starting from the first (the number 2), after including 1 as the first ludic number.\n\n2. **Algorithm Adjustment**: Your function `is_lucid_number` currently checks a different property unrelated to ludic numbers. You'll want to adjust your logic to perform the sieving process described above to generate the sequence of ludic numbers.\n\n3. **Naming Consistency**: Ensure your function names reflect their purpose. Consider changing `lucid_numbers_up_to` to `get_ludic` to align with the problem description and maintain consistency.\n\nImplement the correct algorithm based on these guidelines and test again with the provided test cases. Your understanding and correcting of the approach should lead to successful identification of ludic numbers."
            },
            {
                "role": "assistant",
                "content": "```python\ndef get_ludic_numbers(max_num):\n    ludic_numbers = list(range(1, max_num + 1))\n    index = 1  # Start with the second element (number 2)\n    \n    while index < len(ludic_numbers):\n        step = ludic_numbers[index]\n        ludic_numbers = [num for i, num in enumerate(ludic_numbers) if (i + 1) % step != 0 or i == 0]\n        index += 1\n    \n    return ludic_numbers\n\n# Example usage:\n# ludic_numbers = get_ludic_numbers(100)\n# print(ludic_numbers)\n```"
            },
            {
                "role": "user",
                "content": "Your implementation seems to correctly follow the sieve process for generating ludic numbers. Here are a couple of minor improvements you can make:\n\n1. **Function Naming**: According to the problem statement, the function should be named `get_ludic`. Adjusting the function name can help align more closely with the problem specifications.\n\n2. **Use Included Test Cases**: When you're testing the function, make sure to include the provided test cases to verify that the implementation meets all the requirements.\n\nUpon correcting the function name, your code should pass the given test cases:\n\n```python\n# Example usage with function name adjustment:\ndef get_ludic(max_num):\n    ludic_numbers = list(range(1, max_num + 1))\n    index = 1  # Start with the second element (number 2)\n    \n    while index < len(ludic_numbers):\n        step = ludic_numbers[index]\n        ludic_numbers = [num for i, num in enumerate(ludic_numbers) if (i + 1) % step != 0 or i == 0]\n        index += 1\n    \n    return ludic_numbers\n\n# Test cases\nassert get_ludic(10) == [1, 2, 3, 5, 7]\nassert get_ludic(25) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25]\nassert get_ludic(45) == [1, 2, 3, 5, 7, 11, 13, 17, 23, 25, 29, 37, 41, 43]\n```\n\nWith the name adjusted and test cases verified, everything looks correct. Please proceed with these changes and validate the output."
            },
            {
                "role": "assistant",
                "content": "```python\ndef get_ludic(max_num):\n    ludic_numbers = list(range(1, max_num + 1))\n    index = 1  # Start with the second element (number 2)\n    \n    while index < len(ludic_numbers):\n        step = ludic_numbers[index]\n        ludic_numbers = [num for i, num in enumerate(ludic_numbers) if (i + 1) % step != 0 or i == 0]\n        index += 1\n    \n    return ludic_numbers\n\n# Example usage:\n# ludic_numbers = get_ludic(100)\n# print(ludic_numbers)\n```"
            }
        ],
        "metadata": {
            "original_question": "Write a function to get all lucid numbers smaller than or equal to a given integer.",
            "rephrased_text": "PARAPHRASED QUESTION: Could you provide a Python function that calculates all lucid numbers less than or equal to a specified integer?",
            "taxonomy": [
                {
                    "category": "Coding",
                    "subcategory": ""
                }
            ],
            "annotation_type": [
                "gpt-4o"
            ],
            "language": [
                "en"
            ],
            "tags": [
                "mbpp",
                "reannotate",
                "self-critique"
            ]
        }
    }
]
```