import pandas as pd
import plotly.express as px
import streamlit as st

import utils


def render():
    """Renders the models comparison page."""
    # ---------- Page Config ----------
    title = f"{st.session_state['agent_type']} Comparison Dashboard"
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['page_icon']}{title}</h1>", unsafe_allow_html=True)

    # --- Get models ---
    models = utils.get_models()

    # --- Sidebar ---
    if models:
        selected_models = st.sidebar.multiselect("Select models to compare:", options=models, default=models)
    else:
        st.sidebar.warning("No model folders found in the data directory.")
        selected_models = []

    # --- Collect metrics ---
    results = []
    summaries = []
    for model in selected_models:
        metrics = utils.load_metrics(model)
        model_summaries = utils.load_summaries(model)
        if metrics:
            results.append({"Model": model, **metrics})
        if model_summaries:
            summaries.append({"Model": model, **model_summaries})

    # --- Display results ---
    if results:
        df = pd.DataFrame(results)

        # Sort by step_accuracy in descending order
        df = df.sort_values(by='step_accuracy', ascending=False).reset_index(drop=True)

        st.write("### 🧮 Model Performance Summary")

        # Add bar charts before the table
        st.write("#### 📊 Key Metrics Comparison")
        st.write("*Comparing models on critical performance indicators*")

        cols = st.columns(3)

        # Step Accuracy Chart
        with cols[0]:
            st.markdown("**Step Accuracy**")
            st.caption(
                "Measures how accurately the model predicts both the correct action and parameters for each step")
            df_sorted_step = df.sort_values(by='step_accuracy', ascending=True)
            fig_step = px.bar(
                df_sorted_step,
                x='step_accuracy',
                y='Model',
                orientation='h',
                text_auto=".3f",
                color='step_accuracy',
                color_continuous_scale='Blues'
            )
            fig_step.update_traces(textposition="outside", textfont_size=10)
            fig_step.update_layout(
                xaxis={'range': [0, 1.2], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_step, use_container_width=True)

        # Efficiency Chart
        with cols[1]:
            st.markdown("**Step Efficiency**")
            st.caption(
                "It measures in how many retries the model completes a task relative to the optimal number of retries (fewer retries = higher efficiency)")
            df_sorted_event = df.sort_values(by='efficiency', ascending=True)
            fig_event = px.bar(
                df_sorted_event,
                x='efficiency',
                y='Model',
                orientation='h',
                text_auto=".3f",
                color='efficiency',
                color_continuous_scale='Greens'
            )
            fig_event.update_traces(textposition="outside", textfont_size=10)
            fig_event.update_layout(
                xaxis={'range': [0, 1.2], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_event, use_container_width=True)

        # Mission Success Chart
        with cols[2]:
            st.markdown("**Mission Success Rate**")
            st.caption(
                "Percentage of missions completed successfully from start to finish. Note that at least one retry in each step being successful is the criteria here.")
            df_sorted_mission = df.sort_values(by='mission_success', ascending=True)
            fig_mission = px.bar(
                df_sorted_mission,
                x='mission_success',
                y='Model',
                orientation='h',
                text_auto=".3f",
                color='mission_success',
                color_continuous_scale='Oranges'
            )
            fig_mission.update_traces(textposition="outside", textfont_size=10)
            fig_mission.update_layout(
                xaxis={'range': [0, 1.2], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_mission, use_container_width=True)

        st.write("---")
        st.write("#### 📋 Detailed Metrics Table")

        # # Highlight max in each column
        def highlight_max_cols(s):
            return ['background-color: #d4edda; font-weight: bold' if v == s.max() else '' for v in s]

        score_columns = df.columns.difference(["Model"])
        styled_df = df.style.apply(highlight_max_cols, subset=score_columns).hide(axis='index')

        # Create a boolean DataFrame of max positions
        is_max = df[score_columns] == df[score_columns].max()

        # Count how many times each row has a max value
        max_counts = is_max.sum(axis=1)

        # Get the Model(s) with the highest count
        top_models = df.loc[max_counts == max_counts.max(), "Model"].tolist()
        # Display styled dataframe without index
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        top_model_text = ", ".join(top_models)
        st.markdown(f"**🏆 Top Performing Model:** {top_model_text}", unsafe_allow_html=True)

        if summaries:
            with st.expander("📌Overall AI Summary", expanded=True):
                for _, model_summaries in enumerate(summaries):
                    st.markdown(f"**{model_summaries.get('Model')}:** {model_summaries.get('overall_summary')}")

        # --- Event Identification ---
        with st.expander("📂 Tool Identification", expanded=True):
            st.write(
                "**Tool Identification** measures how well the model recognizes the correct action type (e.g., click, type, scroll) at each step.")
            st.write("")
            cols = st.columns(4)
            metrics = [
                ("Accuracy", "tool_accuracy"),
                ("Precision", "tool_precision"),
                ("Recall", "tool_recall"),
                ("F1", "tool_f1"),
            ]
            for i, (label, col) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"**{label}**")
                    utils.plot_bar_chart(df, "Model", col)

            if summaries:
                st.markdown("---")
                st.markdown("**📌 AI Summary**")
                for _, model_summaries in enumerate(summaries):
                    st.markdown(f"**{model_summaries.get('Model')}:** {model_summaries.get('event_summary')}")

        # --- Step (tool+params) ---
        with st.expander("🧩 Step Completeness", expanded=True):
            st.write(
                "**Step Completeness** evaluates whether the model predicts both the correct action type AND the correct parameters (e.g., coordinates, text to type).")
            st.write("")
            cols = st.columns(4)
            metrics = [
                ("Accuracy", "step_accuracy"),
                ("Precision", "step_precision"),
                ("Recall", "step_recall"),
                ("F1", "step_f1"),
            ]
            for i, (label, col) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"**{label}**")
                    utils.plot_bar_chart(df, "Model", col)

            if summaries:
                st.markdown("---")
                st.markdown("**📌 AI Summary**")
                for _, model_summaries in enumerate(summaries):
                    st.markdown(f"**{model_summaries.get('Model')}:** {model_summaries.get('step_summary')}")

        # --- Pass@k and Pass^k ---
        with st.expander("🎯 Pass@k", expanded=True):
            st.write(
                "**Pass@k** measures the success rate when allowing up to k retry attempts per step, showing the model's ability to recover from errors.")
            st.write("")
            cols = st.columns(3)
            metrics = [
                ("Pass@1", "pass_at_1"),
                ("Pass@2", "pass_at_2"),
                ("Pass@3", "pass_at_3"),
            ]
            for i, (label, col) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"**{label}**")
                    utils.plot_bar_chart(df, "Model", col)

            st.write(
                "**Pass^k** (Pass Power k) measures the success rate when all steps within the first k attempts must be correct, evaluating consistent performance without errors.")
            cols = st.columns(3)
            metrics = [
                ("Pass^1", "pass_power_1"),
                ("Pass^2", "pass_power_2"),
                ("Pass^3", "pass_power_3"),
            ]
            for i, (label, col) in enumerate(metrics):
                with cols[i]:
                    st.markdown(f"**{label}**")
                    utils.plot_bar_chart(df, "Model", col)

            if summaries:
                st.markdown("---")
                st.markdown("**📌 AI Summary**")
                for _, model_summaries in enumerate(summaries):
                    st.markdown(f"**{model_summaries.get('Model')}:** {model_summaries.get('pass_k_summary')}")

        # --- Efficiency ---
        with st.expander("⚙️ Efficiency", expanded=True):
            st.write(
                "**Efficiency** measures in how many retries the model completes a task relative to the optimal number of retries which is 1 (fewer retries = higher efficiency).")
            st.write("")
            utils.plot_bar_chart(df, "Model", "efficiency")

            if summaries:
                st.markdown("---")
                st.markdown("**📌 AI Summary**")
                for _, model_summaries in enumerate(summaries):
                    st.markdown(
                        f"**{model_summaries.get('Model')} Mission Efficiency Summary:** {model_summaries.get('mission_efficiency_summary')}"
                    )

                for _, model_summaries in enumerate(summaries):
                    st.markdown(
                        f"**{model_summaries.get('Model')} Event Efficiency Summary:** {model_summaries.get('event_efficiency_summary')}"
                    )

    else:
        st.info("No valid JSON results found in the selected model folders.")
