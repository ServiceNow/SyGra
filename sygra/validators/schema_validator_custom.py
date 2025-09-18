from sygra.core.graph.graph_config import GraphConfig
from sygra.validators import custom_validations
from sygra.validators.schema_validator_base import SchemaValidator


class CustomSchemaValidator(SchemaValidator):
    def __init__(self, graph_config: GraphConfig):
        """
        Initializes the CustomSchemaValidator with the given YAML file.
        The YAML file should define the schema_config and fields.
        """
        super().__init__(graph_config)  # Call parent constructor to initialize schema and fields

        # You can load other necessary resources here, like custom validations if required
        self.custom_validations = (
            custom_validations  # Make sure to load your custom validation methods
        )
