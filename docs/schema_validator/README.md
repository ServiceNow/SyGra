# Schema Validator

## Introduction

Schema validator enables users to ensure correctness of generated data before uploading to HF or File System.


Key features supported for schema validation are as follows:- 

1. **YAML based schema check:-** Users can define their schema using YAML config files in the following ways:-
   - Define a custom schema class inside `custom_schemas.py` and add it's path in `schema` key inside `schema_config`.
   - Add expected schema config in a list of dict format inside `fields` key inside `schema_config`.
   
2. **Rule based validation support:-** Aside from adding validator rules inside custom class, users can choose from validation methods supported(details in additional validation rules section) and add it as a key for a particular field's dict.
   
## Usage Illustration

Let's assume we have the following record generated which we want to validate:- 

```json
{
        "id": 130426,
        "conversation": [
            {
                "role": "user",
                "content": "I am trying to get the CPU cycles at a specific point in my code."
            },
            {
                "role": "assistant",
                "content": "The `rdtsc` function you're using gives you the number of cycles since the CPU was last reset, which is not what you want in this case."
            }
        ],
        "taxonomy": [
            {
                "category": "Coding",
                "subcategory": ""
            }
        ],
        "annotation_type": [
            "mistral-large"
        ],
        "language": [
            "en"
        ],
        "tags": [
            "glaiveai/glaive-code-assistant-v2",
            "reannotate",
            "self-critique"
        ]
}
```
For the above record, user can have the following class defined inside `custom_schemas.py` defining the 
expected keys and values along with additional validation rules if any. 

```python
class CustomUserSchema(BaseModel):
    '''
    This demonstrates an example of a customizable user schema that can be modified or redefined by the end user.
    Below is a sample schema with associated validator methods.
    '''
    id: int
    conversation: list[dict[str,Any]]
    taxonomy: list[dict[str, Any]]
    annotation_type: list[str]
    language: list[str]
    tags: list[str]

    @root_validator(pre=True)
    def check_non_empty_lists(cls, values):
        if not values.get('id'):
            raise ValueError('id cannot be empty')
        return values
```
#### Sample YAML configuration to use custom schema defined in custom_schemas.py:-

```yaml
schema_config:
  schema: validators.custom_schemas.CustomUserSchema
```
#### Sample YAML configuration to define schema in YAML:-

```yaml
schema_config:
  fields:
    - name: id
      type: int
      is_greater_than: 99999
    - name: conversation
      type: list[dict[str, any]]
    - name: taxonomy
      type: list[dict[str, any]]
    - name: annotation_type
      type: list[str]
    - name: language
      type: list[str]
    - name: tags
      type: list[str]
```
Note that `fields` is expected to be a list of dicts with `name` and `type` present in each dict with additional option
of providing validation key. In the above example `is_greater_than` is a validation key shown for demonstration purpose 
to ensure `id` key in each record has a value with 6 digits or more. 

## Additional Validation Rules Supported:- 

Currently we support the following validation rules that can be directly used by the user:- 

1. `is_greater_than`: Ensures value present in a given field is greater than value provided by user in schema definition. 
2. `is_equal_to`: Ensures value present in a given field is exactly same as value provided by user in schema definition. 
3. `is_less_than`: Ensures value present in a given field is less than value provided by user in schema definition.

More rules will be added in subsequent releases for users to use directly in their schema. 

## Rules for using schema validation:- 

Now that we have covered a sample example on how to define schema and use it, here are some rules users have to keep in mind:- 

1. Schema validation is skipped if `schema_config` key is not present in `graph_config.yaml`. It is assumed that
   user doesn't want schema validation to happen, hence we skip validation check in this case. 
2. If `schema_config` key is present in `graph_config.yaml`, it is expected that either `schema` or `fields` key is present inside `schema_config` and has been defined correctly. Absence of both or invalid definition of `schema` path or `fields` will raise exception. 
3. `type` defined in either `custom_schemas.py` or inside `fields` have to be valid python types. Typo while defining type, for example `lisr` instead of `list` will raise invalid type error stopping the pipeline execution, and user has to re-define correctly. 