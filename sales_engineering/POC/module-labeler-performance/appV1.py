import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime, timedelta
from clarifai.modules.css import ClarifaiStreamlitCSS


# Set page config
st.set_page_config(
    page_title="Labeler Quality and Performance Dashboard", layout="wide"
)
ClarifaiStreamlitCSS.insert_default_css(st)


def colorize_multiselect_options(color: str) -> None:
    # CSS rule to change the background color of the multiselect options
    rules = f"""
    .stMultiSelect div[data-baseweb="select"] span[data-baseweb="tag"] {{
        background-color: {color};
        color: white;  /* Change text color for better contrast */
    }}
    .stMultiSelect div[data-baseweb="select"] span[data-baseweb="tag"]:hover {{
        background-color: {color}; /* Hover effect */
        color: white;  /* Change text color for better contrast */
    }}
    """
    st.markdown(f"<style>{rules}</style>", unsafe_allow_html=True)


# Set the desired color
dark_blue_color = "#0069f9"


# Call the function to apply the color
colorize_multiselect_options(dark_blue_color)


# Define the specific label types
LABEL_TYPES = [
    "Electro-Optical (EO)",
    "Full Motion Video (FMV)",
    "Horizontal Motion Imagery (HMI)",
    "Synthetic Aperture Radar (SAR)",
    "Multi-Modal Data",
    "Natural Language Processing (NLP)",
]
labelers = ["Daniel", "Tara", "Joey", "Teddy", "Spenser"]
concepts = ["HEMITT", "HMMVW", "LMTV", "JLTV"]


# Generate sample data
def generate_sample_data(num_labelers=5, num_days=30, num_concepts=4):
    np.random.seed(42)

    # labelers = [f"Labeler {i+1}" for i in range(num_labelers)]
    dates = [datetime.now().date() - timedelta(days=i) for i in range(num_days)]
    # concepts = [f"Concept {i+1}" for i in range(num_concepts)]

    data = []
    for date in dates:
        for labeler in labelers:
            base_speed = np.random.uniform(10, 20)
            base_quality = np.random.uniform(80, 95)
            improvement_factor = 1 + (num_days - dates.index(date)) / (num_days * 2)

            speed = base_speed * improvement_factor
            quality = min(base_quality * improvement_factor, 100)

            for concept in concepts:
                for label_type in LABEL_TYPES:
                    annotations = int(np.random.normal(25, 5) * improvement_factor)
                    errors = int(annotations * (1 - quality / 100))

                    data.append(
                        {
                            "Date": date,
                            "Labeler": labeler,
                            "Concept": concept,
                            "Label_Type": label_type,
                            "Speed": speed,
                            "Quality": quality,
                            "Annotations": annotations,
                            "Errors": errors,
                            "Error_Rate": (
                                (errors / annotations) * 100 if annotations > 0 else 0
                            ),
                        }
                    )

    return pd.DataFrame(data)


df = generate_sample_data()

# Sidebar filters
st.sidebar.header("Filters")
date_range = st.sidebar.date_input("Date Range", [df["Date"].min(), df["Date"].max()])
selected_labelers = st.sidebar.multiselect(
    "Select Labelers", options=df["Labeler"].unique(), default=df["Labeler"].unique()
)
selected_concepts = st.sidebar.multiselect(
    "Select Concepts", options=df["Concept"].unique(), default=df["Concept"].unique()
)
selected_label_types = st.sidebar.multiselect(
    "Select Label Types", options=LABEL_TYPES, default=LABEL_TYPES
)

# Filter data based on sidebar inputs
filtered_df = df[
    (df["Date"] >= date_range[0])
    & (df["Date"] <= date_range[1])
    & (df["Labeler"].isin(selected_labelers))
    & (df["Concept"].isin(selected_concepts))
    & (df["Label_Type"].isin(selected_label_types))
]
# color = st.color_picker("Pick A Color", "#0069f9")
# st.write("The current color is", color)
# colorize_multiselect_options(color)

# Main content
st.title("Labeler Quality and Performance Dashboard")

# Overall Metrics
st.header("Overall Metrics")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Annotations", f"{filtered_df['Annotations'].sum():,}")
col2.metric("Average Quality Score", f"{filtered_df['Quality'].mean():.2f}%")
col3.metric("Average Error Rate", f"{filtered_df['Error_Rate'].mean():.2f}%")
col4.metric("Avg Labeling Speed", f"{filtered_df['Speed'].mean():.2f} ann/hour")

# Labeler Performance Overview
st.header("Labeler Performance Overview")

# Performance Score Chart
st.subheader("Performance Score Chart")
avg_performance = filtered_df.groupby("Labeler")["Quality"].mean().reset_index()
fig = px.bar(
    avg_performance,
    x="Labeler",
    y="Quality",
    color="Quality",
    color_continuous_scale=["red", "yellow", "green"],
    title="Average Performance Score by Labeler",
)
st.plotly_chart(fig)

# Speed per Annotation
st.subheader("Speed per Annotation")
fig = px.box(
    filtered_df,
    x="Labeler",
    y="Speed",
    color="Labeler",
    title="Distribution of Annotation Speed by Labeler",
)
st.plotly_chart(fig)

# Total Annotations per Period
st.subheader("Total Annotations per Period")
annotations_per_day = (
    filtered_df.groupby(["Date", "Labeler"])["Annotations"].sum().reset_index()
)
fig = px.bar(
    annotations_per_day,
    x="Date",
    y="Annotations",
    color="Labeler",
    title="Total Annotations per Day by Labeler",
)
st.plotly_chart(fig)

# Labeler Efficiency Trend
st.subheader("Labeler Efficiency Trend")
efficiency_trend = (
    filtered_df.groupby(["Date", "Labeler"])["Speed"].mean().reset_index()
)
fig = px.line(
    efficiency_trend,
    x="Date",
    y="Speed",
    color="Labeler",
    title="Labeler Efficiency Trend (Annotations per Hour)",
)
st.plotly_chart(fig)

# Labeler Productivity vs Quality Scatter Plot
st.subheader("Labeler Productivity vs Quality Scatter Plot")
avg_metrics = (
    filtered_df.groupby("Labeler")
    .agg({"Speed": "mean", "Quality": "mean", "Annotations": "sum"})
    .reset_index()
)
fig = px.scatter(
    avg_metrics,
    x="Speed",
    y="Quality",
    size="Annotations",
    hover_name="Labeler",
    color="Labeler",
    title="Labeler Productivity vs Quality",
)
st.plotly_chart(fig)

# Labeler Performance Table
st.subheader("Labeler Performance Table")
performance_table = (
    filtered_df.groupby("Labeler")
    .agg(
        {"Annotations": "sum", "Speed": "mean", "Quality": "mean", "Error_Rate": "mean"}
    )
    .reset_index()
)
performance_table["Trend"] = [
    "↑" if q > 90 else "→" if q > 80 else "↓" for q in performance_table["Quality"]
]
performance_table = performance_table.round(2)
st.table(performance_table)

# Labeler Accuracy per Label Type
st.header("Labeler Accuracy per Label Type")

# Calculate accuracy per label type
accuracy_label_type_df = (
    filtered_df.groupby(["Labeler", "Label_Type"])
    .agg({"Annotations": "sum", "Errors": "sum"})
    .reset_index()
)
accuracy_label_type_df["Accuracy"] = (
    (accuracy_label_type_df["Annotations"] - accuracy_label_type_df["Errors"])
    / accuracy_label_type_df["Annotations"]
    * 100
)

# Heatmap of Labeler Accuracy per Label Type
st.subheader("Labeler Accuracy Heatmap (Label Types)")
fig = px.imshow(
    accuracy_label_type_df.pivot(
        index="Labeler", columns="Label_Type", values="Accuracy"
    ),
    labels=dict(x="Label Type", y="Labeler", color="Accuracy (%)"),
    color_continuous_scale="RdYlGn",
    title="Labeler Accuracy per Label Type",
)
fig.update_layout(height=600)  # Increase height for better readability
st.plotly_chart(fig)

# Bar chart of Accuracy per Label Type for each Labeler
st.subheader("Accuracy per Label Type for each Labeler")
fig = px.bar(
    accuracy_label_type_df,
    x="Label_Type",
    y="Accuracy",
    color="Labeler",
    barmode="group",
    title="Accuracy per Label Type for each Labeler",
)
fig.update_layout(xaxis={"categoryorder": "total descending"})  # Sort by total accuracy
st.plotly_chart(fig)

# Accuracy Trend over Time (Label Types)
st.subheader("Accuracy Trend over Time (Label Types)")
accuracy_trend_label_type = (
    filtered_df.groupby(["Date", "Labeler", "Label_Type"])
    .agg({"Annotations": "sum", "Errors": "sum"})
    .reset_index()
)
accuracy_trend_label_type["Accuracy"] = (
    (accuracy_trend_label_type["Annotations"] - accuracy_trend_label_type["Errors"])
    / accuracy_trend_label_type["Annotations"]
    * 100
)
fig = px.line(
    accuracy_trend_label_type,
    x="Date",
    y="Accuracy",
    color="Labeler",
    facet_col="Label_Type",
    facet_col_wrap=2,
    title="Accuracy Trend over Time by Label Type and Labeler",
)
fig.update_layout(height=800)  # Increase height for better readability
st.plotly_chart(fig)

# Footer
st.sidebar.markdown("---")
st.sidebar.write("© Clarifai - Labeling Quality Dashboard")
