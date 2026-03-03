import pandas as pd
import plotly.express as px
import streamlit as st

import utils


def render():
    """Renders the models comparison page for dynamic flow."""
    # ---------- Page Config ----------
    title = f"{st.session_state['agent_type']} Comparison Dashboard"
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['page_icon']}{title}</h1>", unsafe_allow_html=True)

    if st.session_state.get('selected_benchmark'):
        benchmark = st.session_state['selected_benchmark']
        if benchmark == 'workarena':
            desc = "Models are evaluated using accessibility tree (axtree) only as input modality."
        else:
            desc = "Models are evaluated using either screenshots only or accessibility tree (axtree) only as input modality."
        st.info(f"📋 **Benchmark:** {benchmark.upper()} — {desc}")
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
    for model in selected_models:
        metrics = utils.load_dynamic_overall_data(model)
        if metrics:
            results.append({"Model": model, **metrics})

    # --- Display results ---
    if results:
        df = pd.DataFrame(results)

        # Sort by mission_accuracy in descending order
        df = df.sort_values(by='mission_accuracy', ascending=False).reset_index(drop=True)

        st.write("### 🧮 Model Performance Summary")

        # Add bar charts before the table
        st.write("#### 📊 Key Metrics Comparison")
        st.write("*Comparing models on critical performance indicators*")

        cols = st.columns(3)

        # Mission Accuracy Chart
        with cols[0]:
            st.markdown("**Accuracy (Retry-Level)**")
            st.caption(
                "Measures how accurately the model completes individual retry attempts.")
            df_sorted_step = df.sort_values(by='mission_accuracy', ascending=True)
            fig_step = px.bar(
                df_sorted_step,
                x='mission_accuracy',
                y='Model',
                orientation='h',
                text_auto=".3f",
                color='mission_accuracy',
                color_continuous_scale='Blues'
            )
            fig_step.update_traces(textposition="outside", textfont_size=10)
            fig_step.update_layout(
                xaxis={'range': [0, 1.0], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_step, use_container_width=True)

        # Mission Success Rate Chart
        with cols[1]:
            st.markdown("**Mission Success Rate**")
            st.caption(
                "Percentage of missions that were successful. A mission is considered as successful when at least one retry attempt has succeeded.")
            df_sorted_mission = df.sort_values(by='mission_success_rate', ascending=True)
            fig_mission = px.bar(
                df_sorted_mission,
                x='mission_success_rate',
                y='Model',
                orientation='h',
                text_auto=".3f",
                color='mission_success_rate',
                color_continuous_scale='Purples'
            )
            fig_mission.update_traces(textposition="outside", textfont_size=10)
            fig_mission.update_layout(
                xaxis={'range': [0, 1.0], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_mission, use_container_width=True)

        # Efficiency Chart
        with cols[2]:
            st.markdown("**Efficiency**")
            st.caption(
                "Measures how many steps the model uses relative to maximum allowed (fewer steps = higher efficiency)")
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
                xaxis={'range': [0, 1.0], 'title': ''},
                yaxis={'title': '', 'automargin': True},
                showlegend=False,
                height=300,
                margin={'l': 10, 'r': 70, 't': 20, 'b': 20}
            )
            st.plotly_chart(fig_event, use_container_width=True)

        st.write("---")

        # Display summary statistics
        st.write("#### 📊 Dataset Summary")
        if 'total_records' in df.columns and 'total_missions' in df.columns:
            # Get the first row values (should be same across all models)
            total_records = df['total_records'].iloc[0]
            total_missions = df['total_missions'].iloc[0]

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Missions", f"{int(total_missions)}")
            with col2:
                st.metric("Total Records (Retries)", f"{int(total_records)}")

        st.write("---")
        st.write("#### 📋 Detailed Metrics Table")

        # # Highlight max in each column
        def highlight_max_cols(s):
            return ['background-color: #d4edda; font-weight: bold' if v == s.max() else '' for v in s]

        df2 = df.drop(columns=["total_records", "total_missions", "mean_steps"])
        score_columns = df2.columns.difference(["Model"])
        styled_df = df2.style.apply(highlight_max_cols, subset=score_columns).hide(axis='index')

        # Create a boolean DataFrame of max positions
        is_max = df2[score_columns] == df2[score_columns].max()

        # Count how many times each row has a max value
        max_counts = is_max.sum(axis=1)

        # Get the Model(s) with the highest count
        top_models = df2.loc[max_counts == max_counts.max(), "Model"].tolist()
        # Display styled dataframe without index
        st.dataframe(styled_df, use_container_width=True, hide_index=True)

        top_model_text = ", ".join(top_models)
        st.markdown(f"**🏆 Top Performing Model:** {top_model_text}", unsafe_allow_html=True)

        # --- Accuracy (Mission success rate) ---
        with st.expander("📂 Accuracy", expanded=True):
            st.write(
                "**Accuracy** measures how many times the model completes the task successfully.")
            st.write("")
            st.markdown(f"**Accuracy**")
            utils.plot_bar_chart(df, "Model", "mission_accuracy")

        # --- Mission Success Rate ---
        with st.expander("🎯 Mission Success Rate", expanded=True):
            st.write(
                "**Mission Success Rate** measures the percentage of missions that were successful. A mission is considered as successful when at least one retry attempt has succeeded.")
            st.write("")
            st.markdown(f"**Mission Success Rate**")
            utils.plot_bar_chart(df, "Model", "mission_success_rate")

        # --- Efficiency (mean_steps) ---
        with st.expander("🧩 Efficiency", expanded=True):
            st.write(
                "**Efficiency** is calculated on the basis of number of steps required to complete the task w.r.t. maximum steps allowed (fewer steps = higher efficiency).")
            st.write("")
            st.markdown(f"**Efficiency**")
            utils.plot_bar_chart(df, "Model", "efficiency")

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
    else:
        st.info("No valid JSON results found in the selected model folders.")
