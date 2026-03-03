import streamlit as st
import base64
import io
from PIL import Image
import pandas as pd
import utils


def render():
    """Renders the dynamic desktop evaluation dashboard."""

    # ---------- TITLE ----------
    st.markdown(
        f"<h1 style='text-align: center;'>{st.session_state.get('page_icon', '🖥️⚡')} Dynamic Desktop Mission Viewer</h1>",
        unsafe_allow_html=True)

    # ---------- SIDEBAR ----------
    models = utils.get_models()

    selected_model = st.sidebar.selectbox("Select Model", models)

    # LOAD JSON
    data = utils.load_dynamic_mission_data(selected_model)

    # ---------- SIDEBAR - MISSION SELECTION ----------
    st.sidebar.markdown("---")
    st.sidebar.markdown("## 🔧 Mission Selection")

    # Mission selection - use mission id if available
    mission_options = []
    for i, mission in enumerate(data):
        mission_id = mission.get('id', str(i))
        mission_options.append((i, mission_id))

    selected_mission_idx = st.sidebar.selectbox(
        "📋 Select Mission",
        range(len(mission_options)),
        format_func=lambda x: f"Mission {mission_options[x][1]}"
    )

    # ---------- RETRY SELECTION (for new format) ----------
    mission_data = data[selected_mission_idx] if selected_mission_idx is not None else None

    # Check if this is the new format with all_chat_histories
    is_new_format = mission_data and 'all_chat_histories' in mission_data

    selected_retry = None
    if is_new_format and mission_data:
        retry_keys = list(mission_data.get('all_chat_histories', {}).keys())
        if retry_keys:
            st.sidebar.markdown("---")
            st.sidebar.markdown("## 🔄 Retry Selection")
            selected_retry = st.sidebar.selectbox(
                "🔁 Select Retry",
                retry_keys,
                format_func=lambda
                    x: f"{x.replace('_', ' ').title()} ({mission_data.get('num_steps', {}).get(x, '?')} steps)"
            )

    # Filter options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Display Options")
    show_stats = st.sidebar.checkbox("Show mission summary stats", value=True)
    show_screenshots = st.sidebar.checkbox("Show screenshots", value=True)

    # ---------- MAIN CONTENT ----------
    if selected_mission_idx is not None and mission_data:
        selected_mission_num = int(mission_options[selected_mission_idx][1])

        # Mission Goal
        st.markdown("### 🎯 Mission Goal")
        st.info(mission_data.get('mission', 'No mission description available'))

        # Navigational Directions
        if 'navigational_directions' in mission_data:
            st.markdown("### 🧭 Navigational Directions")
            st.success(mission_data['navigational_directions'])

        # Get the appropriate chat history based on format
        if is_new_format:
            if selected_retry:
                chat_history = mission_data.get('all_chat_histories', {}).get(selected_retry, [])
            else:
                # Default to first retry if none selected
                all_histories = mission_data.get('all_chat_histories', {})
                first_key = list(all_histories.keys())[0] if all_histories else None
                chat_history = all_histories.get(first_key, []) if first_key else []
        else:
            # Old format
            chat_history = mission_data.get('chat_history', [])

        # Extract steps from chat history
        steps = []
        tool_step = 0
        current_step = {}

        # Track the last screenshot for steps without their own
        last_screenshot = None

        for i, turn in enumerate(chat_history):
            role = turn.get('role', '')
            content = turn.get('content', [])

            # Handle new format (user with image_url)
            if role == 'user':
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # New format: image_url in user content
                            if item.get('type') == 'image_url':
                                img_url = item.get('image_url', {}).get('url', '')
                                if img_url.startswith('data:image'):
                                    # Extract base64 data
                                    last_screenshot = img_url.split(',')[1] if ',' in img_url else None
                            # Old format: tool_result
                            elif item.get('type') == 'tool_result':
                                tool_content = item.get('content', [])
                                if isinstance(tool_content, list) and len(tool_content) > 0:
                                    last_item = tool_content[-1]
                                    if isinstance(last_item, dict) and 'source' in last_item:
                                        last_screenshot = last_item.get('source', {}).get('data')

                if last_screenshot and 'screenshot' not in current_step:
                    current_step['screenshot'] = last_screenshot

            elif role == 'assistant':
                # If there's a pending step, save it before starting new one
                if current_step and 'step_id' in current_step:
                    steps.append(current_step.copy())

                tool_step += 1
                current_step = {
                    'step_id': tool_step,
                    'agent_response_text': 'N/A',
                    'agent_tool_call': 'N/A',
                    'agent_tool_call_params': {},
                    'judge_response': 'N/A',
                    'judge_approved': 'N/A'
                }

                # Add last screenshot if available
                if last_screenshot:
                    current_step['screenshot'] = last_screenshot

                # Handle new format (content is string, tool_calls is separate)
                if isinstance(content, str):
                    current_step['agent_response_text'] = content
                    # Check for tool_calls in new format
                    tool_calls = turn.get('tool_calls', [])
                    if tool_calls and len(tool_calls) > 0:
                        tc = tool_calls[0]
                        func = tc.get('function', {})
                        current_step['agent_tool_call'] = func.get('name', 'N/A')
                        try:
                            import json
                            args = func.get('arguments', '{}')
                            current_step['agent_tool_call_params'] = json.loads(args) if isinstance(args, str) else args
                        except:
                            current_step['agent_tool_call_params'] = {'raw': func.get('arguments', '')}
                # Handle old format (content is list)
                elif isinstance(content, list):
                    for content_item in content:
                        if isinstance(content_item, dict):
                            if content_item.get('type') == 'text':
                                current_step['agent_response_text'] = content_item.get('text', 'N/A')
                            elif content_item.get('type') == 'tool_use':
                                current_step['agent_tool_call'] = content_item.get('name', 'N/A')
                                current_step['agent_tool_call_params'] = content_item.get('input', {})

            elif role == 'judge':
                # Update current step with judge info
                if current_step:
                    judge_content = turn.get('content', 'N/A')
                    current_step['judge_response'] = judge_content

                    # Check if judge approved
                    if '<judgement>necessary</judgement>' in str(judge_content):
                        current_step['judge_approved'] = '✅ Approved'
                    elif '<judgement>unnecessary</judgement>' in str(judge_content):
                        current_step['judge_approved'] = '❌ Rejected'
                    else:
                        current_step['judge_approved'] = '⚠️ Unknown'

        # Don't forget to add the last step if it exists
        if current_step and 'step_id' in current_step:
            steps.append(current_step.copy())

        # Filter out Step 1 (initial screenshot) - start from Step 2
        steps = [step for step in steps if step.get('step_id', 0) > 1]

        # ---------- SUMMARY STATS ----------
        if show_stats and steps:
            total_steps = len(steps)
            approved_steps = sum(1 for s in steps if s.get('judge_approved') == '✅ Approved')
            rejected_steps = sum(1 for s in steps if s.get('judge_approved') == '❌ Rejected')
            na_steps = sum(1 for s in steps if s.get('judge_approved') == 'N/A')
            accuracy = (approved_steps / (total_steps - na_steps) * 100) if (total_steps - na_steps) > 0 else 0

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("📊 Total Steps", total_steps)
            col2.metric("✅ Approved Steps", approved_steps)
            col3.metric("❌ Rejected Steps", rejected_steps)
            col4.metric("⚪ Not Evaluated", na_steps)
            col5.metric("🎯 Accuracy (%)", f"{accuracy:.1f}")

            # Show retry info for new format
            if is_new_format:
                st.markdown(
                    f"**Current Retry:** {selected_retry} | **Max Steps Allowed:** {mission_data.get('max_steps', 'N/A')}")

        st.markdown("---")
        st.markdown("### 📋 Step-by-Step Execution")

        # ---------- DISPLAY STEPS ----------
        for step in steps:
            step_id = step.get('step_id', 'Unknown')
            display_step_id = step_id
            if isinstance(step_id, int):
                display_step_id = step_id - 1
            st.markdown(f"#### 🔹 Step {display_step_id}")

            # Display screenshot
            if show_screenshots and 'screenshot' in step:
                try:
                    b64_str = step['screenshot']
                    img_bytes = base64.b64decode(b64_str)
                    bytes_io = io.BytesIO(img_bytes)
                    img = Image.open(bytes_io)
                    st.image(img, caption=f"Step {display_step_id} Screenshot", use_container_width=True)
                except Exception as e:
                    st.warning(f"📸 Screenshot not available: {str(e)}")

            # Get full text values
            agent_text = step.get('agent_response_text', 'N/A')
            judge_text = step.get('judge_response', 'N/A')

            # Create dataframe for step details with truncated preview
            step_data = {
                'Field': [
                    'Agent Response Text',
                    'Agent Tool Call',
                    'Agent Tool Call Params',
                    'Judge Response',
                    'Judge Verdict'
                ],
                'Value': [
                    str(agent_text),
                    step.get('agent_tool_call', 'N/A'),
                    str(step.get('agent_tool_call_params', {})) if step.get('agent_tool_call_params') else 'N/A',
                    str(judge_text),
                    step.get('judge_approved', 'N/A')
                ]
            }

            df = pd.DataFrame(step_data)

            # Style the dataframe
            def highlight_verdict(val):
                if '✅' in str(val):
                    return 'background-color: #b6f7b0; color: black; font-weight: bold;'
                elif '❌' in str(val):
                    return 'background-color: #f7b0b0; color: black; font-weight: bold;'
                elif '⚠️' in str(val):
                    return 'background-color: #fff4b0; color: black; font-weight: bold;'
                return ''

            styled_df = df.style.applymap(
                highlight_verdict,
                subset=['Value']
            ).set_properties(**{
                'white-space': 'pre-wrap',
                'text-align': 'left',
                'vertical-align': 'top',
            })

            st.dataframe(styled_df, use_container_width=True, hide_index=True, height=250)

            st.markdown("---")

        # Final verdict
        if 'judge_verdict' in mission_data and mission_data['judge_verdict']:
            st.markdown("### 🏁 Final Verdict")
            st.write(mission_data['judge_verdict'])

    else:
        st.warning("Please select a mission from the sidebar")