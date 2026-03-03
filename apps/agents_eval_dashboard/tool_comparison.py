import pandas as pd
import streamlit as st

import utils


def render():
    """Renders the event comparison page."""
    # ---------- Page Config ----------
    title = f"{st.session_state['agent_type']} Event Comparison Dashboard"
    st.markdown(f"<h1 style='text-align: center;'>{st.session_state['page_icon']} {title}</h1>", unsafe_allow_html=True)

    # --- Get models ---
    models = utils.get_models()

    # --- Sidebar ---
    if models:
        selected_models = st.sidebar.multiselect("Select models to compare:", options=models, default=models)
    else:
        st.sidebar.warning("No model folders found in the data directory.")
        selected_models = []

    # Get available events from the first model
    available_events = utils.get_available_events(selected_models)

    if not available_events:
        st.warning("No events found in the selected models.")
        return

    # Event selector in sidebar
    st.sidebar.markdown("---")
    selected_event = st.sidebar.selectbox("Select Event:", options=sorted(available_events))

    # --- Collect all metrics for the selected event ---
    results = []

    for model in selected_models:
        event_metrics = utils.load_event_metrics(model, selected_event)
        step_metrics = utils.load_step_metrics(model, selected_event)
        efficiency_metrics = utils.load_event_efficiency(model, selected_event)

        # Combine all metrics into a single row
        row = {"Model": model}

        if event_metrics:
            row.update({
                "event_accuracy": event_metrics.get("accuracy"),
                "event_precision": event_metrics.get("precision"),
                "event_recall": event_metrics.get("recall"),
                "event_f1": event_metrics.get("f1"),
            })

        if step_metrics:
            row.update({
                "step_accuracy": step_metrics.get("step_accuracy"),
                "step_precision": step_metrics.get("step_precision"),
                "step_recall": step_metrics.get("step_recall"),
                "step_f1": step_metrics.get("step_f1"),
            })

        if efficiency_metrics:
            row.update({
                "efficiency": efficiency_metrics.get("step_efficiency"),
            })

        results.append(row)

    # --- Display results ---
    st.markdown(f"## 🎯 Performance Comparison for Event: **{selected_event}**")
    st.markdown("---")

    if results:
        df = pd.DataFrame(results)

        # Sort by step_accuracy in descending order if it exists
        if 'step_accuracy' in df.columns:
            df = df.sort_values(by='step_accuracy', ascending=False).reset_index(drop=True)

        st.write("### 🧮 Model Performance Summary")

        # Highlight max in each column
        def highlight_max_cols(s):
            return ['font-weight: bold' if v == s.max() else '' for v in s]

        score_columns = df.columns.difference(["Model"])
        styled_df = df.style.apply(highlight_max_cols, subset=score_columns).format(precision=4)

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

        # --- Event Identification ---
        with st.expander("📂 Event Identification", expanded=True):
            st.write(f"Comparison of models on **{selected_event}** event identification metrics.")
            cols = st.columns(4)
            metrics = [
                ("Accuracy", "event_accuracy"),
                ("Precision", "event_precision"),
                ("Recall", "event_recall"),
                ("F1", "event_f1"),
            ]
            for i, (label, col) in enumerate(metrics):
                if col in df.columns:
                    with cols[i]:
                        st.markdown(f"**{label}**")
                        utils.plot_bar_chart(df, "Model", col)

        # --- Step Completeness (tool+params) ---
        with st.expander("🧩 Step Completeness", expanded=True):
            st.write(f"Comparison of models on **{selected_event}** step completeness (tool + params) metrics.")
            cols = st.columns(4)
            metrics = [
                ("Accuracy", "step_accuracy"),
                ("Precision", "step_precision"),
                ("Recall", "step_recall"),
                ("F1", "step_f1"),
            ]
            for i, (label, col) in enumerate(metrics):
                if col in df.columns:
                    with cols[i]:
                        st.markdown(f"**{label}**")
                        utils.plot_bar_chart(df, "Model", col)

        # --- Efficiency ---
        with st.expander("⚙️ Efficiency", expanded=True):
            st.write(f"Comparison of models on **{selected_event}** efficiency metric.")
            if "efficiency" in df.columns:
                utils.plot_bar_chart(df, "Model", "efficiency")
            else:
                st.info("No efficiency data available.")

    else:
        st.info(f"No valid metrics found for event **{selected_event}** in the selected model folders.")
