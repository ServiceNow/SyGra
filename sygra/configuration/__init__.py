from sygra.configuration.loader import ConfigLoader


def load_config(config_path):
    """Load workflow from existing YAML configuration."""
    loader = ConfigLoader()
    return loader.load_and_create(config_path)


__all__ = ["ConfigLoader", "load_config"]
