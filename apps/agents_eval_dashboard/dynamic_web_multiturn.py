import streamlit as st
import base64
import io
from PIL import Image
import pandas as pd
import utils


def render():
    """Renders the dynamic web multiturn evaluation dashboard."""

    st.markdown(
        f"<h1 style='text-align: center;'>{st.session_state.get('page_icon', '🌐🔄')} Dynamic Web Multiturn Mission Viewer</h1>",
        unsafe_allow_html=True)

    # Load models
    models = utils.get_models()
    selected_model = st.sidebar.selectbox("Select Model", models)

    # Load data
    output_data = utils.load_multiturn_web_data(selected_model)
    metrics_data = utils.load_multiturn_web_metrics(selected_model)

    # Mission selection
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🎯 Mission Selection")

    mission_ids = list(output_data.keys())
    selected_mission_id = st.sidebar.selectbox(
        "📋 Select Mission",
        mission_ids,
        format_func=lambda x: x.replace("real_eval_", "")
    )

    # Filter options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Display Options")
    show_only_screenshots = st.sidebar.checkbox("Show only steps with screenshots", value=False)

    # Get mission data
    mission_data = output_data[selected_mission_id]
    mission_metrics = next((m for m in metrics_data if m['id'] == selected_mission_id), None)

    # Display mission header
    if mission_metrics:
        mission_name = mission_metrics['info']['task_info']['mission_name']
        n_turns = mission_metrics['info']['task_info']['n_turns']
        total_reward = mission_metrics['reward']
        total_steps = mission_metrics['step']

        st.markdown(f"### 🎯 Mission: {mission_name}")

        col1, col2, col3 = st.columns(3)
        col1.metric("🔄 Total Turns", n_turns)
        col2.metric("🏆 Total Rewards", total_reward)
        col3.metric("📊 Total Steps", total_steps)

        st.markdown("---")

    # Process steps
    steps = mission_data.get('steps', [])

    # Filter steps if checkbox is selected
    if show_only_screenshots:
        steps = [s for s in steps if s.get('turn_complete') and s.get('screenshot')]

    st.markdown("### 📋 Step-by-Step Execution")

    for step in steps:
        step_no = step.get('step_no', 'Unknown')
        st.markdown(f"#### 🔹 Step {step_no}")

        # Get parsed LLM response
        llm_parsed = step.get('llm_parsed', {})
        task_info = step.get('task_info', {})

        # Display turn info with turn goal
        if task_info and mission_metrics:
            turn_idx = task_info.get('turn_idx')
            turn_history = mission_metrics['info']['task_info'].get('turn_history', [])

            # Get turn goal from turn_history
            turn_goal = "N/A"
            if turn_idx is not None and turn_idx < len(turn_history):
                turn_goal = turn_history[turn_idx].get('user', 'N/A')

            st.markdown(f"**Turn:** {turn_idx}")
            st.info(f"**Turn Goal:** {turn_goal}")

        # Get expected value for this step
        expected_value = "N/A"
        if step.get('turn_complete') and step.get('screenshot') and task_info and mission_metrics:
            turn_idx = task_info.get('turn_idx')
            turn_history = mission_metrics['info']['task_info'].get('turn_history', [])
            if turn_idx is not None and turn_idx < len(turn_history):
                expected_value = turn_history[turn_idx].get('expected', 'N/A')

        # Create dataframe for step details
        step_data = {
            'Field': ['Think', 'Plan', 'Memory', 'Action', 'Expected Value'],
            'Value': [
                llm_parsed.get('think', 'N/A'),
                llm_parsed.get('plan', 'N/A'),
                llm_parsed.get('memory', 'N/A'),
                llm_parsed.get('action', 'N/A'),
                expected_value
            ]
        }

        df = pd.DataFrame(step_data)

        # Use styled dataframe with proper wrapping
        styled_df = df.style.set_properties(**{
            'white-space': 'pre-wrap',
            'text-align': 'left',
            'vertical-align': 'top',
        })

        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        # Display screenshot if turn is complete
        if step.get('turn_complete') and step.get('screenshot'):
            try:
                screenshot_data = step['screenshot']
                # Remove data URL prefix if present
                if screenshot_data.startswith('data:image'):
                    screenshot_data = screenshot_data.split(',')[1]

                img_bytes = base64.b64decode(screenshot_data)
                bytes_io = io.BytesIO(img_bytes)
                img = Image.open(bytes_io)
                st.image(img, caption=f"Step {step_no} - Turn Complete Screenshot", use_container_width=True)
                st.success("✅ Turn Completed")
            except Exception as e:
                st.warning(f"📸 Screenshot error: {str(e)}")

        st.markdown("---")