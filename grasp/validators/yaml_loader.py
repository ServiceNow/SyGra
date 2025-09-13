import importlib
from typing import Any, Type

from pydantic import BaseModel

from grasp.validators.type_parser import TypeParser


def parse_type_string(type_str: str) -> Type:
    parser = TypeParser()
    return parser.parse(type_str)


def evaluate_type(type_str: str):
    """
    Evaluates a complex type annotation string and returns the corresponding Python type.
    """
    try:
        return parse_type_string(type_str)
    except ValueError as e:
        raise ValueError(f"Error evaluating type: {str(e)}")


def process_custom_fields(config: dict[str, dict[str, str]]) -> dict[str, Any]:
    """
    Processes the custom fields from YAML, handling nested types like list[list[str]].
    """
    """
       Processes fields from the YAML config, extracting name, type, and additional rules.
       """
    fields = []
    for field in config.get("fields", []):
        try:
            # Initialize the field information dictionary
            field_info = {
                "name": field["name"],
                "type": evaluate_type(str(field["type"])),
            }

            # Add additional keys (e.g., is_greater_than, is_not_empty, etc.) dynamically
            for key, value in field.items():
                if key != "name" and key != "type":
                    field_info[key] = value

            fields.append(field_info)

        except KeyError as e:
            raise KeyError(f"KeyError: Missing expected key {e} in field definition: {field}")
        except TypeError as e:
            raise TypeError[
                f"TypeError: Invalid data type encountered while processing field: {field}. Error: {e}"
            ]
        except Exception as e:
            raise RuntimeError(
                f"Unexpected error occurred while processing field: {field}. Error: {e}"
            )

    return fields


def resolve_schema_class(schema_path: str) -> BaseModel:
    """
    Resolves the schema class from the path.
    Example: "validators.custom_schema.CustomUserSchema" -> CustomUserSchema class.
    """
    try:
        # Split the schema path into module path and class name
        module_path, class_name = schema_path.rsplit(".", 1)
        # Dynamically import the module using importlib
        module = importlib.import_module(module_path)
        # Get the class from the imported module
        schema_class = getattr(module, class_name)
        if not issubclass(schema_class, BaseModel):
            raise ValueError(f"{schema_class} is not a subclass of pydantic.BaseModel")
        return schema_class
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Invalid schema path: {schema_path}") from e
