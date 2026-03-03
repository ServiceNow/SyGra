
import json
import argparse
from pathlib import Path
import os


def main():
    current_user = os.getlogin()
    default_path = f"/Users/{current_user}/Downloads/latest_data"

    parser = argparse.ArgumentParser(description="Static data points collator.")
    parser.add_argument("-p", "--input_path", type=str, default=default_path, help="Absolute path to the dataset.", required=False)
    parser.add_argument("-t", "--task", type=str, default="agents/web_agent_eval", help="task name.", required=False)
    args = parser.parse_args()

    current_path = os.path.abspath(os.getcwd())
    parent_path = "/".join(current_path.split("/")[:-2])
    write_file = f"{parent_path}/{args.task}/static_data_points_collated.json"

    base_dir = Path(args.input_path)  # Convert string to Path object
    all_data = []

    # Iterate over subfolders in ascending order (1 to 30)
    for i in range(1, 31):
        json_file = base_dir / f"scenario_{i}" / "steps_scaled_1000x1000.json"

        if json_file.exists():
            with open(json_file, 'r') as f:
                data = json.load(f)
                all_data.extend(data)  # Use extend instead of append to flatten records
            print(f"Processed: {json_file}")
        else:
            print(f"Warning: {json_file} not found")

    with open(write_file, "w") as f:
        json.dump(all_data, f, indent=4)

    print(f"\nCombined {len(all_data)} records from scenario folders into {write_file}")


if __name__ == "__main__":
    main()
