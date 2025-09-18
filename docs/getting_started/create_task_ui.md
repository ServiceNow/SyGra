
### Run the UI Service

The UI for this project is built using Streamlit and is located in the `apps` directory. To launch the SyGra UI locally, use the provided shell script:

```bash
./run_ui.sh
```

If you're running it for the first time, make sure the script is executable:
```bash
chmod +x run_ui.sh
```

To run it on a custom port (e.g., 8502):
```bash
./run_ui.sh 8502
```
By default, the app will be available at: http://localhost:8501

### Steps to create task

The Streamlit-based user interface provides a comprehensive set of tools to manage models and configure task flows in an interactive manner. Below are the key features:

#### 1. Model Management
Users can view all registered models along with their current status (active or inactive). The interface allows manual refreshing of model statuses to ensure accuracy. Additionally, users can register new models by providing essential details such as base URL, model name, type, and any custom configuration parameters.

#### 2. Review Existing Tasks
Users can explore previously defined task flows through an interactive visual interface. This includes:
- Viewing the task's directed graph structure
- Inspecting individual node configurations
- Understanding the data flow and logic for each task

#### 3. Create a New Task Flow from Scratch
The UI guides users through the complete process of creating a new task flow:
- Filling in `data_config` parameters
- Constructing the task graph by defining nodes and edges
- Defining the `output_config` section
- Automatically generating the required `graph_config.yaml` and `task_executor.py` files
- Reviewing and publishing the complete task setup

#### 4. Create a New Task Flow Based on Existing Flows
Users can use existing task flows as templates, modify them as needed, and publish new customized task flows. This streamlines the task creation process by leveraging previously defined components.

---