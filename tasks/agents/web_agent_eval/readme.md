# Web Agent Evaluation Guide

## 🚀 Running the Evaluation

### Prerequisites
Run the convert tools folder code files as mentioned to generate `chat_history_seed.json` in `tasks/agents/web_agent_eval/`.

### Configuration
Set the model name in `graph_config.yaml` before running the evaluation.

### Execution
Run the `tasks/agents/web_agent_eval` task. This generates three output files:

1. **`output_{timestamp}.json`**
   - Contains golden responses and model responses for each retry

2. **`MetricCollatorPostProcessor_{timestamp}.json`**
   - Overall metrics, efficiency scores, and AI-generated summaries
   - Sample: `apps/agents_eval_dashboard/data/web_agents/model_name_1/MetricCollatorPostProcessor_2025-12-15_17-15-22.json`

3. **`mission_data_{timestamp}.json`**
   - Detailed evaluation results for each retry of every mission
   - Sample: `apps/agents_eval_dashboard/data/web_agents/model_name_1/mission_data_2025-12-15_17-15-22.json`

---

## 📊 Visualizing Results

### Setup
1. Navigate to `apps/agents_eval_dashboard/data/web_agents/`
2. Create a folder with your model name (e.g., `model_name_1`)
3. Copy the generated `MetricCollatorPostProcessor_{timestamp}.json` and `mission_data_{timestamp}.json` files into this folder

### Launch Dashboard
```bash
cd apps/agents_eval_dashboard
streamlit run app.py
```

### Dashboard contents
1. Once the dashboard loads, inside there, select "Web Agents(Static)" as the Eval_type to view the results. 
2. Inside this page you select the type of dashboard you want view. There will be 4 types of dashboard:
    - Web Agents overall comparison dashboard: This will show the overall evaluation results across all models.
    - Web Agents model details dashboard: This will shows the detailed evaluation results for a specific selected model.
    - Web Agents Tool comparison: This will show the performance of all models for a specific selected tool/action.
    - Mission Dashboard: This will show the detailed results for each step of a selected mission for a particular selected model. This is useful for developers who want to view/debug the model response for certain steps of specific missions in order to analyze the model failures.
3. The below screenshot shows the sample view of the dashboard:
![img_1.png](img_1.png)


