import argparse

from sygra.tools.executor import ToolExecutor
from sygra.tools.registry import ToolRegistry


def main():
    parser = argparse.ArgumentParser(description="Dataset Tools CLI")
    parser.add_argument("--config", help="Path to YAML config file")
    parser.add_argument("--list-tools", action="store_true", help="List all registered tools")

    args = parser.parse_args()

    # Discover tools before doing anything else
    ToolRegistry.auto_discover()

    if args.list_tools:
        tools = ToolRegistry.list_tools()
        print("\n📋 Available tools:\n")
        for name, desc in tools.items():
            print(f" - {name}: {desc}")
        return 0

    if args.config:
        try:
            print(f"\n⚙️  Running tools from config: {args.config}")
            executor = ToolExecutor(args.config)
            final_output = executor.execute()
            print(f"\nTool execution completed.\nFinal output saved to: {final_output}")
            return 0
        except Exception as e:
            print(f"\nTool execution failed: {e}")
            return 1

    print("No valid arguments. Use --list-tools or --config <file>")
    return 1
