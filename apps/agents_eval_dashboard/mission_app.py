import json
import os

import pandas as pd
import streamlit as st
from PIL import Image

import utils


def render():
    """Renders the mission details page."""
    # ---------- PAGE CONFIG ----------
    title = f"{st.session_state['agent_type']} Mission Data Viewer"
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['page_icon']}{title}</h1>", unsafe_allow_html=True)

    # ---------- SIDEBAR ----------
    models = utils.get_models()

    selected_model = st.sidebar.selectbox("Select Model", models)

    # LOAD JSON
    data = utils.load_mission_data(selected_model)

    # Sort mission IDs chronologically (mission_01, mission_02, …)
    def mission_sort_key(mid):
        """Function to sort mission id."""
        num = "".join([c for c in mid if c.isdigit()])
        return int(num) if num else 0

    mission_ids = sorted(data.keys(), key=mission_sort_key)
    selected_mission_id = st.sidebar.selectbox("Select Mission ID", mission_ids)

    # Filter options
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Filter Options")

    only_incorrect = st.sidebar.checkbox("Show only incorrect steps")
    show_stats = st.sidebar.checkbox("Show mission summary stats", value=True)

    # ---------- MAIN CONTENT ----------
    if selected_mission_id:
        mission_entries = data[selected_mission_id]

        if mission_entries:
            # Mission description
            mission_text = mission_entries[0].get("mission", "No mission text found.")
            st.markdown("### 📝 Mission Description")
            st.info(mission_text)

            # Flatten JSON into table
            rows = []
            for step in mission_entries:
                for r in step["results"]:
                    try:
                        if r["retry_data"]["tool_calls"][0].get("function"):
                            predicted_params = r["retry_data"]["tool_calls"][0]["function"]["arguments"]
                        else:
                            predicted_params = r["retry_data"]["tool_calls"][0]["input"]
                    except Exception:
                        predicted_params = {}

                    predicted_params_display = predicted_params
                    try:
                        if isinstance(predicted_params, (dict, list)):
                            predicted_params_display = json.dumps(predicted_params, ensure_ascii=False)
                    except Exception:
                        predicted_params_display = str(predicted_params)

                    # Handle both desktop and web agents field names
                    # Desktop: golden_tool, golden_resposne (typo)
                    # Web: golden_event, golden response (with space)
                    golden_event = r.get("golden_event") or r.get("golden_tool", "N/A")
                    predicted_event = r.get("predicted_event") or r.get("predicted_tool", "N/A")

                    # Check which key exists for golden response/response
                    golden_response = None
                    if "golden response" in r:
                        golden_response = r["golden response"]
                    elif "golden_response" in r:
                        golden_response = r["golden_response"]
                    elif "golden_resposne" in r:
                        golden_response = r["golden_resposne"]

                    if isinstance(golden_response, dict):
                        golden_response_list = [golden_response]
                    elif isinstance(golden_response, list):
                        golden_response_list = [g for g in golden_response if isinstance(g, dict)]
                    else:
                        golden_response_list = []

                    golden_params = []
                    for g in golden_response_list:
                        props = g.get("properties", {})
                        if props == {}:
                            props = g.get("tool_input", {})
                        if not isinstance(props, dict):
                            continue
                        event_name = g.get("event", "")
                        if not event_name or event_name == "N/A":
                            event_name = golden_event if isinstance(golden_event, str) else ""
                        golden_params.append({"event": event_name, "properties": props})

                    rows.append(
                        {
                            "Step ID": step["step_id"],
                            "Retry ID": r["retry_id"],
                            "Golden Tool": golden_event,
                            "Predicted Tool": predicted_event,
                            "Golden Parameters": json.dumps(golden_params, ensure_ascii=False) if isinstance(
                                golden_params, list) else json.dumps(golden_params, ensure_ascii=False) if isinstance(
                                golden_params, dict) else str(golden_params),
                            "Golden Parameters Raw": golden_params,
                            "Predicted Parameters": predicted_params_display,
                            "Predicted Parameters Raw": predicted_params,
                            "Tool Correct": r["tool_correct"],
                            "Params Correct": r["params_correct"],
                            "Step Correct": r["step_correct"],
                        }
                    )

            df = pd.DataFrame(rows)

            # Sort chronologically by step number
            df["Step Number"] = df["Step ID"].str.extract(r"_(\d+)$").astype(int)
            df = df.sort_values(["Step Number", "Retry ID"]).drop(columns=["Step Number"]).reset_index(drop=True)

            # Deduplicate within each step and keep top 3 rows max
            df = (
                df.groupby("Step ID", as_index=False, group_keys=False)
                .apply(lambda g: g.head(3))
                .reset_index(drop=True)
            )

            # Apply filters
            if only_incorrect:
                df = df[~df["Step Correct"]]

            # ---------- SUMMARY STATS ----------
            if show_stats:
                total_steps = df["Step ID"].nunique()
                correct_steps = df[df["Step Correct"]]["Step ID"].nunique()
                accuracy = (correct_steps / total_steps * 100) if total_steps > 0 else 0

                col1, col2, col3 = st.columns(3)
                col1.metric("Total Steps", total_steps)
                col2.metric("Correct Steps", correct_steps)
                col3.metric("Accuracy (%)", f"{accuracy:.1f}")

            st.markdown("---")
            st.markdown("### 📊 Step Results (Chronological Order)")

            # ---------- HELPERS ----------
            def emoji_bool(val):
                """Function to convert bool to symbols."""
                if isinstance(val, bool):
                    return "✅" if val else "❌"
                return val

            def highlight_bool(val):
                """Function to highlight bool."""
                if val == "✅":
                    return "background-color: #b6f7b0; color: black;"
                elif val == "❌":
                    return "background-color: #f7b0b0; color: black;"
                return ""

            # ---------- DISPLAY TABLES ----------
            for step_id, group in df.groupby("Step ID", sort=False):
                # Guarantee max 3 rows per step
                group = group.head(3).reset_index(drop=True)

                st.markdown(f"#### 🧩 Step ID: `{step_id}`")
                # Path to your image
                mission_num = int(selected_mission_id.split("_")[-1])
                step_num = int(step_id.split("_")[-1])
                folder_path = st.session_state['folder_path']
                step_path = st.session_state['step_path']
                diff = st.session_state['image_step_diff']
                step_id2 = step_num - diff
                image_path = f"{folder_path}/scenario_{mission_num}/{step_path}step_{step_id2}{st.session_state['suffix']}.png"
                golden_event = df.loc[df['Step ID'] == step_id, 'Golden Tool'].iloc[0]
                golden_bbox = df.loc[df['Step ID'] == step_id, 'Golden Parameters Raw'].iloc[0]
                pred_params_list = df.loc[df['Step ID'] == step_id, 'Predicted Parameters Raw']
                # Load the image (optional, but allows resizing, etc.)
                if os.path.exists(image_path):
                    image = Image.open(image_path)
                    image = utils.draw_bbox_on_image(
                        image,
                        golden_bbox,
                        golden_event,
                        pred_params_list,
                        color_gld='yellow',
                        color_pred='red',
                        width=3,
                        label=None,
                    )
                    st.image(image, caption=step_id + " Image")
                else:
                    st.warning("📸 Screenshot not available.")

                display_df = group.copy()
                for col in ["Tool Correct", "Params Correct", "Step Correct"]:
                    display_df[col] = display_df[col].apply(emoji_bool)

                styled_df = (
                    display_df.drop(columns=["Step ID", "Golden Parameters Raw", "Predicted Parameters Raw"])
                    .style.applymap(highlight_bool, subset=["Tool Correct", "Params Correct", "Step Correct"])
                    .set_properties(
                        **{
                            "white-space": "pre-wrap",
                            "text-align": "left",
                            "vertical-align": "top",
                        }
                    )
                )

                # Display table (hide index, exactly 3 rows)
                st.dataframe(styled_df, use_container_width=True, hide_index=True, height=200)
                st.markdown("---")
