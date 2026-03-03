import importlib
import os

import streamlit as st

username = os.getlogin()

# ---------- Page Config ----------
st.set_page_config(page_title="Agents Evaluation Dashboard", layout="wide", page_icon="📊")

# ---------- Agent Type Selection ----------
st.sidebar.title("🎬 Eval Dashboard")
agent_type = st.sidebar.selectbox(
    "Select Eval Type:",
    ["Web Agents (Static)", "Desktop Agents (Static)", "Desktop Agents (Dynamic)", "Web Agents (Dynamic)", "Web Agents (Dynamic Multiturn)"],
)

data_dir=""
st.session_state['selected_benchmark'] = None

# Set the data directory based on agent type
if agent_type == "Web Agents (Static)":
    data_dir = "data/web_agents"
    agent_label = "Web Agents"
    image_path = f"/Users/{username}/Downloads/latest_data"
    step_path = ""
    image_step_diff = 1
    page_icon = "🌐"
    suffix = "_scaled_1000x1000"
    eval_mode = "static"
elif agent_type == "Desktop Agents (Static)":
    data_dir = "data/desktop_agents"
    agent_label = "Desktop Agents"
    image_path = f"/Users/{username}/Downloads/workflows"
    step_path = "steps/"
    image_step_diff = 2
    page_icon = "🖥️"
    suffix = ""
    eval_mode = "static"
elif agent_type == "Desktop Agents (Dynamic)":
    data_dir = "data/dynamic_desktop"
    agent_label = "Dynamic Desktop"
    image_path = None
    step_path = None
    image_step_diff = None
    page_icon = "🖥️⚡"
    suffix = None
    eval_mode = "dynamic_desktop"
elif agent_type == "Web Agents (Dynamic Multiturn)":
    data_dir = "data/dynamic_multiturn_web"
    agent_label = "Dynamic Web Multiturn"
    image_path = None
    step_path = None
    image_step_diff = None
    page_icon = "🌐🔄"
    suffix = None
    eval_mode = "dynamic_web_multiturn"

# Store in session state for access by other modules
st.session_state['data_dir'] = data_dir

if agent_type == "Web Agents (Dynamic)":  # Web Agents (Dynamic)
    data_dir = "data/dynamic_web"
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_data_path = os.path.join(current_dir, data_dir)
    benchmarks = [f.name for f in os.scandir(base_data_path) if f.is_dir() and not f.name.startswith('.')]
    if benchmarks:
        selected_benchmark = st.sidebar.selectbox("Select Benchmark:", sorted(benchmarks))
        st.session_state['data_dir'] = f"{data_dir}/{selected_benchmark}"
        st.session_state['selected_benchmark'] = selected_benchmark

    agent_label = "Dynamic Web"
    image_path = None
    step_path = None
    image_step_diff = None
    page_icon = "🌐⚡"
    suffix = None
    eval_mode = "dynamic_web"


st.session_state['agent_type'] = agent_label
st.session_state['folder_path'] = image_path
st.session_state['step_path'] = step_path
st.session_state['image_step_diff'] = image_step_diff
st.session_state['page_icon'] = page_icon
st.session_state['suffix'] = suffix
st.session_state['eval_mode'] = eval_mode

st.sidebar.markdown("---")

# ---------- Dashboard Selection ----------
if eval_mode == "static":
    PAGES = {
        f"{agent_label} Overall Comparison": "model_comparison",
        f"{agent_label} Model Details": "model_details_app",
        f"{agent_label} Tool Comparison": "tool_comparison",
        f"{agent_label} Mission Viewer": "mission_app",
    }
elif eval_mode == "dynamic_desktop":  # dynamic mode
    PAGES = {
        f"{agent_label} Overall Comparison": "dynamic_model_comparison",
        f"{agent_label} Mission Viewer": "dynamic_desktop",
    }
elif eval_mode == "dynamic_web_multiturn":
    PAGES = {
        f"Dynamic Web Multiturn Mission Viewer": "dynamic_web_multiturn",
        f"Browser Use Results": "browser_use_cua",
    }
else:  # dynamic_web o industry benchmark
    PAGES = {
        f"{agent_label} Overall Comparison": "dynamic_model_comparison",
    }

page = st.sidebar.selectbox("Select a dashboard", list(PAGES.keys()))
module = importlib.import_module(PAGES[page])
module.render()