import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from PIL import ImageDraw, ImageFont


def get_data_dir():
    """Get the current data directory from session state."""
    # Get the directory where this utils.py file is located
    current_dir = os.path.dirname(os.path.abspath(__file__))
    relative_data_dir = st.session_state.get('data_dir', 'data/web_agents')
    # Construct absolute path
    return os.path.join(current_dir, relative_data_dir)


def get_models(path=None):
    """Function to load models folders."""
    if path is None:
        path = get_data_dir()
    return [f.name for f in os.scandir(path) if f.is_dir()]


def load_data(selected_model, file_prefix):
    """Function to load eval data."""
    data_dir = get_data_dir()
    folder = Path(os.path.join(data_dir, selected_model))

    # Find all files matching the pattern
    files = list(folder.glob(file_prefix + "*.json"))
    if not files:
        print(f"No {file_prefix} files found.")
        return None

    def extract_timestamp(file_path):
        """Extract datetime object from filename like mission_data_2025-10-28_22-45-23.json."""
        try:
            timestamp_str = file_path.stem.replace(file_prefix + "_", "")
            return datetime.strptime(timestamp_str, "%Y-%m-%d_%H-%M-%S")
        except ValueError:
            return None

    # Filter valid files and find the latest by timestamp
    valid_files = [(f, extract_timestamp(f)) for f in files]
    valid_files = [(f, ts) for f, ts in valid_files if ts is not None]

    if not valid_files:
        # Just take the first matching file (no timestamp needed)
        latest_file = files[0]

    else:
        latest_file, _ = max(valid_files, key=lambda x: x[1])

    # Read JSON data
    with open(latest_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Loaded data from: {latest_file.name}")
    return data


def load_mission_data(selected_model):
    """Function to load mission data."""
    return load_data(selected_model, "mission_data")


def load_eval_data(selected_model):
    """Function to load eval data."""
    return load_data(selected_model, "Metric")


def load_dynamic_mission_data(selected_model):
    """Function to load mission data."""
    return load_data(selected_model, "output")


def load_dynamic_overall_data(selected_model):
    """Function to load overall eval data for dynamic flow."""
    return load_data(selected_model, "overall_metrics")

def load_multiturn_web_data(selected_model):
    """Function to load multiturn web mission data."""
    return load_data(selected_model, "output_combined")

def load_multiturn_web_metrics(selected_model):
    """Function to load multiturn web overall metrics."""
    return load_data(selected_model, "overall_metrics")


# --- Safe nested dictionary getter ---
def safe_get(dct, path, default=None):
    """Get data dict safely."""
    for key in path:
        if isinstance(dct, dict) and key in dct:
            dct = dct[key]
        else:
            return default
    return dct


# ---------- Helper: Plot Metrics by Subsection ----------
def plot_metrics_by_subsection(data, index_col_name="Type", chart_titles=("accuracy", "precision", "recall", "f1")):
    """Plot Accuracy, Precision, Recall, F1 as separate charts (side by side) with subsections on X-axis."""
    df = pd.DataFrame(data).T.reset_index().rename(columns={"index": index_col_name})

    cols = st.columns(len(chart_titles))  # 4 charts in one row

    for i, chart_title in enumerate(chart_titles):
        with cols[i]:
            plot_bar_chart(df, index_col_name, chart_title)


def plot_bar_chart(df, x_axis_col, y_axis_col):
    """Function to plot bar chart."""
    fig = px.bar(
        df,
        x=x_axis_col,
        y=y_axis_col,
        text_auto=".3f",
        color=x_axis_col,  # Different color for each type
        color_discrete_sequence=px.colors.qualitative.Prism + px.colors.qualitative.Antique,
    )
    fig.update_traces(textposition="inside", textfont_size=12)
    fig.update_layout(
        title={"text": f"{y_axis_col.capitalize()}", "font": {"size": 14}, "x": 0.5},
        yaxis={"range": [0, 1], "title": ""},
        xaxis={"title": ""},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 10, "r": 10, "t": 40, "b": 20},
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def plot_retry_chart(df, x_axis_col, title):
    """Function to plot retry charts for eval metrics."""
    fig_steps = px.bar(
        df.melt(id_vars=x_axis_col, value_vars=["total_step_count", "retry_step_count"]),
        x=x_axis_col,
        y="value",
        color="variable",
        barmode="group",
        text="value",
        color_discrete_sequence=px.colors.qualitative.G10,
        labels={"value": "Count", "variable": "Step Type"},
    )
    fig_steps.update_traces(textposition="outside", textfont_size=12)
    fig_steps.update_layout(
        title={"text": title, "font": {"size": 14}, "x": 0.5},
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    st.plotly_chart(fig_steps, use_container_width=True)


# --- Load metrics from JSON ---
def load_metrics(model):
    """Load metrics from model data."""
    try:
        data = load_eval_data(model)
        if not data:
            return None
        event_avg = safe_get(data[0], ["results", "overall", "event(tool)", "average"], {})
        step_avg = safe_get(data[0], ["results", "overall", "step(tool+params)", "average"], {})
        efficiency_avg = safe_get(data[0], ["results", "efficiency", "average"], {})
        pass_k = safe_get(data[0], ["results", "overall", "pass_k", "average"], {})

        # Calculate mission success rate, which was originally missing
        mission_data = safe_get(data[0], ["results", "mission"], {})
        total_missions = 0
        successful_missions = 0
        for mission_key, mission_info in mission_data.items():
            if isinstance(mission_info, dict) and "successful" in mission_info:
                total_missions += 1
                if mission_info.get("successful"):
                    successful_missions += 1

        mission_success_rate = successful_missions / total_missions if total_missions > 0 else 0

        return {
            "tool_accuracy": event_avg.get("accuracy"),
            "tool_precision": event_avg.get("precision"),
            "tool_recall": event_avg.get("recall"),
            "tool_f1": event_avg.get("f1"),
            "step_accuracy": step_avg.get("accuracy"),
            "step_precision": step_avg.get("precision"),
            "step_recall": step_avg.get("recall"),
            "step_f1": step_avg.get("f1"),
            "efficiency": efficiency_avg.get("step_efficiency"),
            "mission_success": mission_success_rate,
            "pass_at_1": pass_k.get("1").get("pass_at_k"),
            "pass_at_2": pass_k.get("2").get("pass_at_k"),
            "pass_at_3": pass_k.get("3").get("pass_at_k"),
            "pass_power_1": pass_k.get("1").get("pass_power_k"),
            "pass_power_2": pass_k.get("2").get("pass_power_k"),
            "pass_power_3": pass_k.get("3").get("pass_power_k")
        }
    except Exception as e:
        st.warning(f"Error reading metrics for {model}: {e}")
        return None


def get_short_summary(summary):
    """Get short summary."""
    short_summary = summary.split("Short Summary:")[-1]

    if short_summary == summary:
        short_summary = summary.split("\n")[-1]
    return short_summary.replace("**", "").replace("\n", "")


def load_summaries(model):
    """Load summary from model data."""
    try:
        data = load_eval_data(model)
        if not data:
            return None
        ai_summary = safe_get(data[0], ["results", "ai_summary"], {})
        return {
            "overall_summary": get_short_summary(ai_summary.get("overall")),
            "event_summary": get_short_summary(ai_summary.get("Event Identification")),
            "step_summary": get_short_summary(ai_summary.get("Step Completeness")),
            "event_efficiency_summary": get_short_summary(ai_summary.get("Event Efficiency")),
            "mission_efficiency_summary": get_short_summary(ai_summary.get("Mission Efficiency")),
            "pass_k_summary": get_short_summary(ai_summary.get("Pass K"))
        }
    except Exception as e:
        st.warning(f"Error reading ai_summary from {model}: {e}")
        return None


def get_available_events(models):
    """Get list of all available events from the selected models."""
    events = set()
    for model in models:
        try:
            data = load_eval_data(model)
            if not data:
                continue
            event_tool = safe_get(data[0], ["results", "overall", "event(tool)"], {})
            for key in event_tool.keys():
                if key != "average":  # Skip the average key
                    events.add(key)
        except Exception as e:
            st.warning(f"Error reading events from {model}: {e}")
    return list(events)


def load_event_metrics(model, event):
    """Load event identification metrics for a specific event."""
    try:
        data = load_eval_data(model)
        if not data:
            return None
        event_data = safe_get(data[0], ["results", "overall", "event(tool)", event], {})
        if not event_data:
            return None
        return {
            "accuracy": event_data.get("accuracy"),
            "precision": event_data.get("precision"),
            "recall": event_data.get("recall"),
            "f1": event_data.get("f1"),
        }
    except Exception as e:
        st.warning(f"Error reading event metrics for {model}, event {event}: {e}")
        return None


def load_step_metrics(model, event):
    """Load step completeness metrics for a specific event."""
    try:
        data = load_eval_data(model)
        if not data:
            return None
        step_data = safe_get(data[0], ["results", "overall", "step(tool+params)", event], {})
        if not step_data:
            return None

        return {
            "step_accuracy": step_data.get("accuracy"),
            "step_precision": step_data.get("precision"),
            "step_recall": step_data.get("recall"),
            "step_f1": step_data.get("f1"),
        }
    except Exception as e:
        st.warning(f"Error reading step metrics for {model}, event {event}: {e}")
        return None


def load_event_efficiency(model, event):
    """Load efficiency metrics for a specific event."""
    try:
        data = load_eval_data(model)
        if not data:
            return None
        efficiency_data = safe_get(data[0], ["results", "efficiency", event], {})
        if not efficiency_data:
            return None
        return {
            "total_step_count": efficiency_data.get("total_step_count"),
            "retry_step_count": efficiency_data.get("retry_step_count"),
            "step_efficiency": efficiency_data.get("step_efficiency"),
        }
    except Exception as e:
        st.warning(f"Error reading efficiency for {model}, event {event}: {e}")
        return None


def draw_golden_bbox(draw, golden_bbox, color_gld):
    if not golden_bbox or not isinstance(golden_bbox, dict):
        return

    props = golden_bbox
    if 'properties' in golden_bbox and isinstance(golden_bbox.get('properties'), dict):
        props = golden_bbox.get('properties', {})

    if isinstance(props, dict) and props.get('bbox') is not None:
        bbox = props.get('bbox')

    bbox = None
    if isinstance(props, dict):
        bbox = props.get('bbox')
    if isinstance(bbox, dict):
        props = bbox
    elif isinstance(bbox, list) and len(bbox) > 0 and isinstance(bbox[0], dict):
        props = bbox[0]

    if not isinstance(props, dict):
        return

    if all(k not in props for k in ('x', 'y', 'width', 'height')):
        return

    # if isinstance(bbox, dict):
    #     props = bbox
    # elif isinstance(bbox, list) and len(bbox) > 0 and isinstance(bbox[0], dict):
    #     props = bbox[0]

    # if not isinstance(props, dict):
    #     return

    x = props.get('x', 0)
    y = props.get('y', 0)
    w = props.get('width', 0)
    h = props.get('height', 0)

    if w is None or h is None:
        return

    # Calculate rectangle coordinates
    x1, y1 = x, y
    x2, y2 = x + w, y + h

    # Draw rectangle
    draw.rectangle([x1, y1, x2, y2], outline=color_gld, width=3)


def draw_bbox_on_image(image, golden_bbox, golden_event, pred_params_list, color_gld='green', color_pred='red', width=3,
                       label=None):
    """
    Draw a golden bounding box and retry points on an image.

    Args:
        image: PIL Image object
        golden_bbox: Dictionary with keys 'x', 'y', 'width', 'height' for the golden bbox
        golden_event: String containing the golden event
        pred_params_list: pandas Series or list of dictionaries containing predicted parameters for each retry
                         Each dict should have 'x' and 'y' keys (can be in JSON string format)
        color_gld: Color of the golden bounding box (default: 'green')
        color_pred: Color of the retry points (default: 'red')
        width: Width of the bounding box lines (default: 3)
        label: Optional text label (not used in current implementation)

    Returns:
        PIL Image object with bounding box and retry points drawn
    """
    if image is None:
        return image

    # Create a copy to avoid modifying the original
    img_copy = image.copy()
    draw = ImageDraw.Draw(img_copy)

    if isinstance(golden_bbox, list):
        for el in golden_bbox:
            draw_golden_bbox(draw, el, color_gld)
    else:
        draw_golden_bbox(draw, golden_bbox, color_gld)

    # Draw golden bounding box
    # if golden_event == "click" or golden_event == "typing":
    # for el in golden_bbox:
    #     if el:
    #         x = el.get('x', 0)
    #         y = el.get('y', 0)
    #         w = el.get('width', 0)
    #         h = el.get('height', 0)

    #         # Calculate rectangle coordinates
    #         x1, y1 = x, y
    #         x2, y2 = x + w, y + h

    #         # Draw rectangle
    #         draw.rectangle([x1, y1, x2, y2], outline=color_gld, width=width)

    # Draw retry points
    if pred_params_list is not None:
        try:
            font = ImageFont.load_default()
            point_radius = 8

            # Convert to list if it's a pandas Series
            if hasattr(pred_params_list, 'tolist'):
                retry_params = pred_params_list.tolist()
            else:
                retry_params = list(pred_params_list)

            # Draw each retry point
            for idx, params in enumerate(retry_params):
                if params:
                    # Parse JSON string if needed
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except:
                            continue

                    # Extract x, y coordinates
                    pred_x = params.get('x')
                    pred_y = params.get('y')

                    if pred_x is not None and pred_y is not None:
                        # Convert to float if they're strings
                        try:
                            pred_x = float(pred_x)
                            pred_y = float(pred_y)
                        except (ValueError, TypeError):
                            continue

                        # Draw circle at the point
                        draw.ellipse(
                            [pred_x - point_radius, pred_y - point_radius,
                             pred_x + point_radius, pred_y + point_radius],
                            fill=color_pred,
                            outline=color_pred
                        )

                        # Draw label (r0, r1, r2, etc.)
                        retry_label = f"r{idx}"

                        # Position label slightly offset from the point
                        label_x = pred_x + point_radius + 5
                        label_y = pred_y - point_radius - 5

                        # Draw label background
                        text_bbox = draw.textbbox((label_x, label_y), retry_label, font=font)
                        draw.rectangle(text_bbox, fill=color_pred)
                        draw.text((label_x, label_y), retry_label, fill='white', font=font)

        except Exception as e:
            # If there's any error processing retry points, just return the image with golden bbox
            st.warning(f"Error drawing retry points: {e}")

    return img_copy
