import pandas as pd
import streamlit as st


def render():
    """Renders the model results comparison page across benchmarks."""

    title = "Model Results Comparison"
    st.markdown(f"<h1 style='text-align: center;'>📊 {title}</h1>", unsafe_allow_html=True)

    st.write("### 🤖 AI Summary")
    st.info("""
    **Summary:** This analysis compares model performance across diverse web environments using DOM + IMAGE modality.

    **Key Findings:**

    1. **Both models tied overall, but on very different strengths.** Gemini led on Omnizon (35% vs 18%) — better at transactional tasks like purchasing and product matching. Claude led on DashDish (44% vs 11%) — better at multi-turn contextual reasoning, time/price calculations, and filtering.

    2. **Neither model can reliably complete large-scale enumeration tasks.** Tasks requiring extraction and counting of >20 items from filtered result sets were never fully completed. Gemini stopped at ~12 of 64 products; Claude at ~45. Neither agent planned or persisted effectively.
    """)

    st.write("---")

    st.write("### 📊 Model Performance by Benchmark")
    st.caption("Performance shown as percentage of successful task completions")

    data = {
        'Model': ['claude sonnet 4.5', 'gemini 2.5 pro preview'],
        'OMNIZON (DOM + IMAGE)': ['18%', '35%'],
        'DASHDISH (DOM + IMAGE)': ['44%', '11%']
    }

    df = pd.DataFrame(data)

    def highlight_max_percentage(s):
        if s.name == 'Model':
            return [''] * len(s)

        percentages = []
        for val in s:
            try:
                percentages.append(float(val.strip('%')))
            except (ValueError, AttributeError):
                percentages.append(0.0)

        max_val = max(percentages)
        return [
            'background-color: #d4edda; font-weight: bold' if val == max_val else ''
            for val in percentages
        ]

    styled_df = df.style.apply(highlight_max_percentage).hide(axis='index')

    st.dataframe(styled_df, use_container_width=True, hide_index=True)

    st.write("---")

    st.write("### 📈 Performance Insights")

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            label="Best OMNIZON Performance",
            value="gemini 2.5 pro preview",
            delta="35%"
        )

    with col2:
        st.metric(
            label="Best DASHDISH Performance",
            value="claude sonnet 4.5",
            delta="44%"
        )

    st.write("---")

    with st.expander("ℹ️ About the Benchmarks", expanded=False):
        st.write("""
        **OMNIZON (DOM + IMAGE):** E-commerce platform testing environment focusing on product search, 
        filtering, and purchase workflows with DOM tree and screenshot inputs.

        **DASHDISH (DOM + IMAGE):** Food delivery platform evaluation suite testing restaurant discovery, 
        menu navigation, and order placement capabilities with multimodal inputs.

        **Metrics:** Percentages represent the ratio of successfully completed tasks to total tasks attempted 
        in each benchmark environment.
        """)

