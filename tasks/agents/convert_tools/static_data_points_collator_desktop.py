
import json
import argparse
from pathlib import Path
import os


def main():
    current_user = os.getlogin()
    default_path = f"/Users/{current_user}/Downloads/workflows"

    parser = argparse.ArgumentParser(description="Static data points collator.")
    parser.add_argument("-p", "--input_path", type=str, default=default_path, help="Absolute path to the dataset.", required=False)
    parser.add_argument("-t", "--task", type=str, default="agents/desktop_agent_eval", help="task name.", required=False)
    args = parser.parse_args()

    current_path = os.path.abspath(os.getcwd())
    parent_path = "/".join(current_path.split("/")[:-2])
    write_file = f"{parent_path}/{args.task}/static_data_points_collated.json"

    base_dir = Path(args.input_path)  # Convert string to Path object
    if not base_dir.exists():
        print(f"Error: Input path {base_dir} does not exist")
        return

    all_data = []
    processed_count = 0
    skipped_folders = []

    # Get all subdirectories, excluding __pycache__ and other non-workflow folders
    folders = sorted([f for f in base_dir.iterdir()
                      if f.is_dir() and f.name != "__pycache__"])

    print(f"Found {len(folders)} folders to process in {base_dir}\n")

    ## Iterate over all folders
    for folder in folders:
        json_file = folder / "steps_processed.json"

        if json_file.exists():
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        all_data.extend(data)
                    else:
                        all_data.append(data)
                processed_count += 1
                print(f"✓ Processed: {folder.name}/step_processed.json ({len(data) if isinstance(data, list) else 1} records)")
            except json.JSONDecodeError as e:
                print(f"✗ Error reading {folder.name}/step_processed.json: {e}")
                skipped_folders.append(folder.name)
        else:
            print(f"⚠ Warning: {folder.name}/step_processed.json not found")
            skipped_folders.append(folder.name)

    with open(write_file, "w") as f:
        json.dump(all_data, f, indent=4)

    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  - Total folders found: {len(folders)}")
    print(f"  - Successfully processed: {processed_count}")
    print(f"  - Skipped/Failed: {len(skipped_folders)}")
    print(f"  - Total records combined: {len(all_data)}")
    print(f"  - Output file: {write_file}")

    print(f"\nCombined {len(all_data)} records from workflow folders into {write_file}")

    if skipped_folders:
        print(f"\nSkipped folders: {', '.join(skipped_folders)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
