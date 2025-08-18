# Data Quality

## Introduction

**Data Quality** enables users to add data quality metrics to the generated output records. This is particularly useful for evaluating the performance of models and ensuring that the generated data meets specific quality standards.


### Key Features

1. **YAML-Based Configuration**  
   Users can specify the data quality metrics they want to include in the output records by modifying the `data_quality` section in the configuration file.
2. **Automatic injection of quality in OASST data**
    The quality metrics can be automatically injected directly into output records following the OASST format without any additional configuration.
---

## Default Behavior

By default, the Data Quality feature is **disabled**. To enable it, add the following runtime argument:

```
--quality True
````

The default configuration is specified in the `configuration.yaml` file:

```yaml
    data_quality:
      tasks:
          - name: "conversation_pretokenization"
            params:
              hf_chat_template_model_id: "Qwen/Qwen2.5-32B-Instruct"
          - name: "metadata_tagging"
          - name: "llm_based_quality"
          - name: "data_characteristics"
            params:
              model: "Qwen/Qwen2.5-32B-Instruct"
          - name: "language_tagging"
          - name: "lexical_diversity"
          - name: "ppl_score"
            params:
              model_config:
                model_type: "vllm"  # or "tgi"
                url: # model url
                model_serving_name: "qwen-32B"
```
### Configuration Parameters
- `skip_failed_tasks`: When set to `true`, the processor will continue execution even if individual data quality tasks fail. When `false`, the processor will stop on the first task failure. Default is `true`.
- `tasks`: A list of tasks to be performed for data quality assessment. Each task can have its own parameters.

## Available Tasks
The following data quality tasks are available:
1. conversation_pretokenization: Performs pre-tokenization on conversation data.
2. metadata_tagging: Tags records with metadata.
3. llm_based_quality: Assesses quality using LLM-based metrics.
4. data_characteristics: Extracts characteristics from data like token counts and turn numbers.
5. language_tagging: Identifies and tags the language of the text.
6. lexical_diversity: Computes lexical diversity metrics (TTR - Type-Token Ratio).
7. ppl_score: Calculates perplexity scores for text quality assessment.
   
    `Note`: You need to host the model first and share the URL in the parameters.
8. reward_score: Calculates reward scores from the reward model. (Offline setup)

    `Note`: This task requires running the codebase in an environment with a GPU, or using a reward model compatible with CPU execution.

---

## Usage Illustration

You can run the Data Quality in two modes:

#### 1. Default Mode

Run with:

```
--oasst True
```

This uses the configuration specified in `configuration.yaml`

#### 2. Overridden Mode

To override the default behavior, modify the `output_config` section in your `graph_config.yaml` file like so:

```yaml
output_config:
    data_quality:
        tasks:
            - name: "metadata_tagging"
            - name: "llm_based_quality"
```
This will make the data quality to run only for the specified tasks.

The input data can be in conversation or in OASST format. The Data Quality feature will automatically inject the specified quality metrics into the output records.

### Output Example

The example below is for default mode. The overridden mode will have the same format but with different data quality metrics based on the configuration

#### Conversation data
```json
[
  {
        "id": "3056af5d",
        "conversation": [
            {
                "role": "user",
                "content": "I have a field that contains a string of numbers like \"2002 2005 2001 2006 2008 2344\". I know how to select a substring using the `SELECT substr(years,1,4)  FROM TABLE` query, but I'm struggling to check each substring individually. My goal is to find the row that contains the number closest to 0. Is there a way to achieve this using SQL?"
            },
            {
                "role": "assistant",
                "content": "To find the number closest to 0 in a string of space-separated numbers within a SQL query, you can use a combination of string functions and a common table expression (CTE) or a subquery to split the string and then find the minimum absolute value. Here's an example using a CTE in SQLite:\n\n```sql\nWITH RECURSIVE SplitNumbers AS (\n  SELECT\n    CAST(SUBSTR(years, 1, INSTR(years || ' ', ' ') - 1) AS INTEGER) AS number,\n    SUBSTR(years, INSTR(years || ' ', ' ') + 1) AS remaining\n  FROM\n    your_table\n  UNION ALL\n  SELECT\n    CAST(SUBSTR(remaining, 1, INSTR(remaining || ' ', ' ') - 1) AS INTEGER),\n    SUBSTR(remaining, INSTR(remaining || ' ', ' ') + 1)\n  FROM\n    SplitNumbers\n  WHERE\n    remaining != ''\n)\nSELECT\n  number\nFROM\n  SplitNumbers\nORDER BY\n  ABS(number)\nLIMIT 1;\n```\n\nReplace `your_table` with the actual name of your table and `years` with the actual column name. This query will split the string into individual numbers, convert them to integers, and then find the number with the smallest absolute value."
            }
        ],
        "data_quality_metadata": {
            "data_taxonomy": {
                "category": "Code Writing",
                "subcategory": "",
                "instruction_tags": [
                    "SQL Query Help",
                    "Data Processing",
                    "Problem Solving"
                ]
            },
            "data_quality": {
                "llm_based": {
                    "question_quality_score": 4,
                    "explanation_question_quality": "The prompt is well-articulated and clear, with a specific goal of finding the number closest to 0 in a string of numbers using SQL. It demonstrates a good understanding of SQL functions and expresses the user's struggle effectively. The grammar is correct, and the question is relevant to SQL operations, though it could benefit from more depth in terms of exploring potential solutions.",
                    "response_quality": {
                        "instruction_following": 5,
                        "explanation_instruction_following": "The response follows the instruction to find the number closest to 0 from a string of numbers using SQL.",
                        "accuracy": 5,
                        "explanation_accuracy": "The response accurately provides a SQL query that splits the string into individual numbers and finds the number closest to 0.",
                        "relevance": 5,
                        "explanation_relevance": "The response is directly relevant to the query, focusing on solving the problem of finding the number closest to 0.",
                        "clarity": 5,
                        "explanation_clarity": "The response is clear and well-structured, with a step-by-step explanation of the SQL query.",
                        "completeness": 5,
                        "explanation_completeness": "The response is complete, providing a full SQL solution and instructions on how to adapt it to the user's table and column names.",
                        "conciseness": 5,
                        "explanation_conciseness": "The response is concise, providing all necessary information without unnecessary details.",
                        "overall_score": 5.0
                    }
                }
            },
            "data_characteristics": {
                "num_turns": 2,
                "num_tokens": 371,
                "num_input_tokens": 92,
                "num_target_tokens": 279
            }
        }
    }
]
```

#### OASST data
```json
[
  {
    "conversation_id": "3056af5d",
    "message_id": "msg_1_59a96096",
    "parent_id": null,
    "root_message_id": "msg_1_59a96096",
    "message_level": 1,
    "role": "user",
    "content": "...",
    ...
  },
  {
    "conversation_id": "conv_8513aa73",
    "message_id": "msg_2_e8b221e8",
    "parent_id": "msg_1_59a96096",
    "root_message_id": "msg_1_59a96096",
    "message_level": 2,
    "role": "assistant",
    "content": "...",
    "quality": {
        "quality_characteristics_LLM_based_question_quality_score": 4,
        "quality_characteristics_LLM_based_explanation_question_quality": "The prompt is well-articulated and clear, with a specific goal of finding the number closest to 0 in a string of numbers using SQL. It demonstrates a good understanding of SQL functions and expresses the user's struggle effectively. The grammar is correct, and the question is relevant to SQL operations, though it could benefit from more depth in terms of exploring potential solutions.",
        "quality_characteristics_LLM_based_response_quality_instruction_following": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_instruction_following": "The response follows the instructions by providing a SQL query to find the number closest to 0 from a string of numbers.",
        "quality_characteristics_LLM_based_response_quality_accuracy": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_accuracy": "The response accurately uses SQL functions and CTEs to split the string and find the minimum absolute value, which aligns with the query requirements.",
        "quality_characteristics_LLM_based_response_quality_relevance": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_relevance": "The response is directly relevant to the query, focusing on the task of finding the number closest to 0 using SQL.",
        "quality_characteristics_LLM_based_response_quality_clarity": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_clarity": "The response is clear and well-structured, with a step-by-step explanation of the SQL query process.",
        "quality_characteristics_LLM_based_response_quality_completeness": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_completeness": "The response is complete, addressing all parts of the query and providing a full SQL solution.",
        "quality_characteristics_LLM_based_response_quality_conciseness": 5,
        "quality_characteristics_LLM_based_response_quality_explanation_conciseness": "The response is concise, providing necessary information without unnecessary verbosity.",
        "quality_characteristics_LLM_based_response_quality_overall_score": 5.0
    },
    "data_characteristics": {
        "num_turns": 2,
        "num_tokens": 381,
        "num_input_tokens": 92,
        "num_target_tokens": 289
    },
    ...
  }
]
```

---

## Rules for Using Data Quality

1. **Default Behavior**: The default behavior is to run the data quality tasks as specified in the `configuration.yaml` file.
2. **Overridden Mode**: You can override the default behavior by modifying the `output_config` section in your `graph_config.yaml` file. This will allow you to specify which tasks to run and their parameters.
3. **Input Data Format**: The input data can be in conversation or OASST format. The Data Quality feature will automatically inject the specified quality metrics into the output records.
4. **Output Format**: The output format will depend on the input data format. If the input data is in conversation format, the output will be in conversation format. If the input data is in OASST format, the output will be in OASST format.
