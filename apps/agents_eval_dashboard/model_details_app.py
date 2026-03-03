import pandas as pd
import streamlit as st

import utils


def render():
    """Renders the model details page."""
    # ---------- Page Config ----------
    title = f"{st.session_state['agent_type']} Model Details Dashboard"
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['page_icon']}{title}</h1>", unsafe_allow_html=True)

    # ---------- SIDEBAR ----------
    models = utils.get_models()
    selected_model = st.sidebar.selectbox("Select Model", models)

    # ---------- Load Data ----------
    data = utils.load_eval_data(selected_model)

    overall = data[0]["results"]["overall"]
    ai_summary = data[0]["results"].get("ai_summary")

    # ---------- Section: General (tool) ----------
    with st.expander("📌 Tool Identification", expanded=True):
        event_tool = overall["event(tool)"]
        utils.plot_metrics_by_subsection(event_tool)
        if ai_summary and "Event Identification" in ai_summary:
            st.markdown("---")
            st.markdown("**📌 AI Summary**")
            st.write(ai_summary.get("Event Identification"))

    # ---------- Section: Specific (tool+params) ----------
    with st.expander("📌 Tool Execution (Step Completeness)", expanded=True):
        step_tool = overall["step(tool+params)"]
        utils.plot_metrics_by_subsection(step_tool)
        if ai_summary and "Step Completeness" in ai_summary:
            st.markdown("---")
            st.markdown("**📌 AI Summary**")
            st.write(ai_summary.get("Step Completeness"))

    # ---------- Section: Mission Efficiency ----------
    with st.expander("📌 Mission Efficiency", expanded=True):
        missions = data[0]["results"]["mission"]

        # Convert dict → DataFrame
        mission_df = pd.DataFrame(missions).T.reset_index().rename(columns={"index": "Mission"})
        mission_df["Mission Number"] = mission_df["Mission"].str.extract(r"_(\d+)$").astype(int)
        mission_df = mission_df.sort_values("Mission Number").drop(columns=["Mission Number"]).reset_index(drop=True)

        # Success as Yes/No
        mission_df["successful"] = mission_df["successful"].apply(lambda x: "✅ Yes" if x else "❌ No")

        # Show table
        st.write("### 🔹 Mission Data Table")
        st.dataframe(
            mission_df.style.format(
                {"total_step_count": "{:.0f}", "retry_step_count": "{:.0f}", "step_efficiency": "{:.2f}"}
            )
        )

        # Step Efficiency Bar Chart
        st.write("### 📊 Step Efficiency by Mission")
        utils.plot_bar_chart(mission_df, "Mission", "step_efficiency")

        # Total vs Retry Steps
        st.write("### 📊 Total vs Retry Steps by Mission")
        utils.plot_retry_chart(mission_df, "Mission", "Total vs Retry Steps per Mission")

        if ai_summary and "Mission Efficiency" in ai_summary:
            st.markdown("---")
            st.markdown("**📌 AI Summary**")
            st.write(ai_summary.get("Mission Efficiency"))

    # ---------- Section: Event Efficiency ----------
    with st.expander("📌 Event Efficiency", expanded=True):
        efficiency = data[0]["results"]["efficiency"]

        # Convert dict → DataFrame
        efficiency_df = pd.DataFrame(efficiency).T.reset_index().rename(columns={"index": "Event"})

        # Step Efficiency Bar Chart
        st.write("### 📊 Step Efficiency by Event")
        utils.plot_bar_chart(efficiency_df, "Event", "step_efficiency")

        # Total vs Retry Steps
        st.write("### 📊 Total vs Retry Steps by Event")
        utils.plot_retry_chart(efficiency_df, "Event", "Total vs Retry Steps per Event")

        if ai_summary and "Event Efficiency" in ai_summary:
            st.markdown("---")
            st.markdown("**📌 AI Summary**")
            st.write(ai_summary.get("Event Efficiency"))

    # ---------- Section: AI Summary ----------
    if ai_summary and "overall" in ai_summary:
        with st.expander("📌 AI Overall Summary", expanded=True):
            st.write(ai_summary.get("overall"))
