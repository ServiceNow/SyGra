### Output Record Generator

The Output Record Generator is a flexible component that translates the final state of the graph into the desired output format for each record. 

#### Key Concept: 
Configure the final record fields in a YAML block (called `output_map`), telling the generator how to map fields from the graph's state or use static values—and optionally apply transforms.

#### Usage: 

In the `graph_config.yaml`, declare an `output_config` section specifying a `generator`, such as `processors.output_record_generator.CodeGenOutputGenerator`

#### 1. Simple Derived Class
Subclass the `BaseOutputGenerator` and implement the `generate()` method that returns the final record from the state. 

Example:

- YAML Configuration
```yaml
output_config:
  generator: processors.output_record_generator.CodeGenOutputGenerator
```

- Python Code
```python
class CodeGenOutputGenerator(BaseOutputGenerator):
    def generate(self, state: GraphState) -> dict[str, Any]:
      if "messages" not in state:
          return None

      chat_format_messages = utils.convert_messages_from_langchain_to_chat_format(
          state["messages"]
      )
      if (
          len(chat_format_messages) < 1
          or "no more feedback"
          not in chat_format_messages[-1]["content"].lower().strip()
      ):
          return None
      # remove the last message if it contains "no more feedback"
      chat_format_messages = chat_format_messages[:-1]
      chat_format_messages.insert(
          0,
          {
              "role": "user",
              "content": state["rephrased_text"].replace(
                  "PARAPHRASED QUESTION: ", ""
              ),
          },
      )
      return {
          "id": state.get("id", ""),
          "conversation": chat_format_messages,
          "taxonomy": [{"category": "Coding", "subcategory": ""}],
          "annotation_type": ["mistral-large"],
          "language": ["en"],
          "tags": ["mbpp", "reannotate", "self-critique"],
      }
```


#### 2. YAML driven Mapping & Transform

In this approach, we define a YAML configuration that maps fields from the graph's state or uses static values—and optionally apply transforms.

Example:

- YAML Configuration

```yaml
output_config:
  generator: processors.output_record_generator.CodeGenOutputGenerator

  output_map:
    id:
      from: "id"  # Copy from state["id"]
    conversation:
      from: "messages"
      transform: "build_conversation"  # Apply a transform method on state["messages"]
    taxonomy:
      value:
        - category: "Coding"  # Hard-coded literal value
          subcategory: ""
    annotation_type:
      value: [ "mistral-large" ]   # Hard-coded literal list
    language:
      value: "en"   # Hard-coded literal value
    tags:
      value: ["mbpp", "reannotate", "self-critique"]   # Hard-coded literal list
```

- Python Code
```python
class CodeGenOutputGenerator(BaseOutputGenerator):
    """
    Example specialized generator class, which defines a transform method
    for building a conversation from messages, removing 'no more feedback', etc.
    """

    @staticmethod
    def build_conversation(data: Any, state: dict[str, Any]) -> Any:
        chat_format_messages = utils.convert_messages_from_langchain_to_chat_format(data)
        
        # Example logic:
        if (
            not chat_format_messages
            or "no more feedback" not in chat_format_messages[-1]["content"].lower().strip()
        ):
            return None
        
        # remove the last message
        chat_format_messages.pop()

        # insert rephrased question if available
        if "rephrased_text" in state and state["rephrased_text"]:
            question = state["rephrased_text"].replace("PARAPHRASED QUESTION: ", "")
            chat_format_messages.insert(0, {"role": "user", "content": question})

        return chat_format_messages
```

- `generator`: The dotted Python path to the output generator class (e.g., `CodeGenOutputGenerator`).
- `output_map`: Each key (e.g., id, conversation, tags) **will become a field in the final record.**
  - `from`: Means “read from the in-memory `state` with that key.”
  - `value`: Means “use this literal value.”
  - `transform`: Means “call a method on the generator class to transform the data.” This is optional.

Note: If we include `"transform": "my_custom_logic"` in the YAML, you then a method named `my_custom_logic` must be defined in the generator class. 

Here, we define a `build_conversation` method that takes the `data` and `state` as arguments and returns the transformed conversation.