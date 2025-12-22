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
# Modified generate_sample_data function
def generate_sample_data(num_days=90):
    np.random.seed(42)
    dates = [datetime.now().date() - timedelta(days=i) for i in range(num_days)]

    data = []
    for date in dates:
        for labeler in labelers:
            base_speed = np.random.uniform(18, 25)
            base_quality = np.random.uniform(80, 95)
            improvement_factor = 1 + (num_days - dates.index(date)) / (num_days * 2)

            manual_speed = base_speed * improvement_factor
            manual_quality = min(base_quality * improvement_factor, 100)

            for concept in concepts:
                for label_type in LABEL_TYPES:
                    annotations = int(np.random.normal(25, 5) * improvement_factor)

                    # Manual labeling data
                    manual_errors = int(annotations * (1 - manual_quality / 100))
                    data.append(
                        {
                            "Date": date,
                            "Labeler": labeler,
                            "Concept": concept,
                            "Label_Type": label_type,
                            "Labeling_Type": "Manual",
                            "Speed": manual_speed,
                            "Quality": manual_quality,
                            "Annotations": annotations,
                            "Errors": manual_errors,
                            "Error_Rate": (
                                (manual_errors / annotations) * 100
                                if annotations > 0
                                else 0
                            ),
                            "Time_Taken": annotations / manual_speed,
                        }
                    )

                    # Model-assisted labeling data
                    assisted_speed = manual_speed * 1.5  # 50% speed increase
                    assisted_quality = min(
                        manual_quality * 1.03, 100
                    )  # 3% quality increase (industry standard)
                    assisted_errors = int(
                        manual_errors * 0.7
                    )  # 30% error reduction (industry standard)
                    data.append(
                        {
                            "Date": date,
                            "Labeler": labeler,
                            "Concept": concept,
                            "Label_Type": label_type,
                            "Labeling_Type": "Model-Assisted",
                            "Speed": assisted_speed,
                            "Quality": assisted_quality,
                            "Annotations": annotations,
                            "Errors": assisted_errors,
                            "Error_Rate": (
                                (assisted_errors / annotations) * 100
                                if annotations > 0
                                else 0
                            ),
                            "Time_Taken": annotations / assisted_speed,
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

# Main content
st.title("Labeler Quality and Performance Dashboard")

# Create tabs
tab1, tab2 = st.tabs(
    [
        "Manual Labeling State",
        "Model-Assisted Labeling",
    ]
)

with tab1:
    # Current State Dashboard (existing code)
    st.header("Manual Labeling Performance")

    # Filter for manual labeling only
    manual_df = filtered_df[filtered_df["Labeling_Type"] == "Manual"]

    # Overall Metrics
    st.subheader("Overall Metrics")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Annotations", f"{manual_df['Annotations'].sum():,}")
    col2.metric("Average Quality Score", f"{manual_df['Quality'].mean():.2f}%")
    col3.metric("Average Error Rate", f"{manual_df['Error_Rate'].mean():.2f}%")
    col4.metric("Avg Labeling Speed", f"{manual_df['Speed'].mean():.2f} ann/hour")

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
            {
                "Annotations": "sum",
                "Speed": "mean",
                "Quality": "mean",
                "Error_Rate": "mean",
            }
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
    fig.update_layout(
        xaxis={"categoryorder": "total descending"}
    )  # Sort by total accuracy
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

with tab2:
    st.header("Model-Assisted Labeling")

    # Filter for model-assisted labeling
    model_assisted_df = filtered_df[filtered_df["Labeling_Type"] == "Model-Assisted"]
    manual_df = filtered_df[filtered_df["Labeling_Type"] == "Manual"]

    # Overall Metrics Comparison
    st.subheader("Overall Metrics Comparison")
    col1, col2, col3, col4 = st.columns(4)

    manual_annotations = manual_df["Annotations"].sum()
    model_annotations = model_assisted_df["Annotations"].sum()
    col1.metric(
        "Total Annotations",
        f"{model_annotations:,}",
        f"{(model_annotations - manual_annotations) / manual_annotations:.1%}",
    )

    manual_quality = manual_df["Quality"].mean()
    model_quality = model_assisted_df["Quality"].mean()
    col2.metric(
        "Average Quality Score",
        f"{model_quality:.2f}%",
        f"{(model_quality - manual_quality) / manual_quality:.1%}",
    )

    manual_error = manual_df["Error_Rate"].mean()
    model_error = model_assisted_df["Error_Rate"].mean()
    col3.metric(
        "Average Error Rate",
        f"{model_error:.2f}%",
        f"{(manual_error - model_error) / manual_error:.1%}",
    )

    manual_speed = manual_df["Speed"].mean()
    model_speed = model_assisted_df["Speed"].mean()
    col4.metric(
        "Avg Labeling Speed",
        f"{model_speed:.2f} ann/hour",
        f"{(model_speed - manual_speed) / manual_speed:.1%}",
    )

    # Time Savings
    st.subheader("Time Savings with Model-Assisted Labeling")
    time_comparison = (
        filtered_df.groupby("Labeling_Type")["Time_Taken"].sum().reset_index()
    )
    time_savings = (
        1
        - time_comparison.loc[
            time_comparison["Labeling_Type"] == "Model-Assisted", "Time_Taken"
        ].values[0]
        / time_comparison.loc[
            time_comparison["Labeling_Type"] == "Manual", "Time_Taken"
        ].values[0]
    ) * 100
    st.metric("Time Reduction", f"{time_savings:.1f}%", "↓")

    fig = px.bar(
        time_comparison,
        x="Labeling_Type",
        y="Time_Taken",
        title="Total Time Taken: Model-Assisted vs Manual Labeling",
        color="Labeling_Type",
        labels={"Time_Taken": "Total Time (hours)", "Labeling_Type": "Labeling Method"},
    )
    st.plotly_chart(fig)

    # Error Rate Reduction
    st.subheader("Error Rate Reduction")
    error_reduction = (manual_error - model_error) / manual_error * 100
    st.metric("Error Rate Reduction", f"{error_reduction:.1f}%", "↓")

    error_comparison = (
        filtered_df.groupby("Labeling_Type")["Error_Rate"].mean().reset_index()
    )
    fig = px.bar(
        error_comparison,
        x="Labeling_Type",
        y="Error_Rate",
        title="Average Error Rate: Model-Assisted vs Manual Labeling",
        labels={"Error_Rate": "Error Rate (%)", "Labeling_Type": "Labeling Method"},
        color="Labeling_Type",
        color_discrete_map={"Manual": "red", "Model-Assisted": "green"},
    )
    st.plotly_chart(fig)

    # Speed Improvement
    st.subheader("Labeling Speed Improvement")
    speed_improvement = (model_speed - manual_speed) / manual_speed * 100
    st.metric("Speed Increase", f"{speed_improvement:.1f}%", "↑")

    speed_comparison = (
        filtered_df.groupby("Labeling_Type")["Speed"].mean().reset_index()
    )
    fig = px.bar(
        speed_comparison,
        x="Labeling_Type",
        y="Speed",
        title="Average Labeling Speed: Model-Assisted vs Manual Labeling",
        labels={
            "Speed": "Speed (annotations/hour)",
            "Labeling_Type": "Labeling Method",
        },
        color="Labeling_Type",
        color_discrete_map={"Manual": "blue", "Model-Assisted": "green"},
    )
    st.plotly_chart(fig)

    # [Rest of the code for tab2 remains the same]
    # New section: Error Rate Reduction
    st.subheader("Error Rate Reduction")
    error_reduction = (manual_error - model_error) / manual_error * 100
    st.metric("Error Rate Reduction", f"{error_reduction:.1f}%", "↓")

    error_comparison = (
        filtered_df.groupby("Labeling_Type")["Error_Rate"].mean().reset_index()
    )
    fig = px.bar(
        error_comparison,
        x="Labeling_Type",
        y="Error_Rate",
        title="Average Error Rate: Model-Assisted vs Manual Labeling",
        labels={"Error_Rate": "Error Rate (%)", "Labeling_Type": "Labeling Method"},
        color="Labeling_Type",
        color_discrete_map={"Manual": "red", "Model-Assisted": "green"},
    )
    st.plotly_chart(fig)

    # Error Rate Over Time
    st.subheader("Error Rate Trend")
    error_trend = (
        filtered_df.groupby(["Date", "Labeling_Type"])["Error_Rate"]
        .mean()
        .reset_index()
    )
    fig = px.line(
        error_trend,
        x="Date",
        y="Error_Rate",
        color="Labeling_Type",
        title="Error Rate Trend: Model-Assisted vs Manual Labeling",
        labels={"Error_Rate": "Error Rate (%)", "Date": "Date"},
    )
    st.plotly_chart(fig)

    # Efficiency Over Time
    st.subheader("Labeling Efficiency Over Time")
    efficiency_over_time = (
        filtered_df.groupby(["Date", "Labeling_Type"])["Speed"].mean().reset_index()
    )
    fig = px.line(
        efficiency_over_time,
        x="Date",
        y="Speed",
        color="Labeling_Type",
        title="Labeling Efficiency Over Time",
        labels={"Speed": "Average Speed (annotations/hour)", "Date": "Date"},
    )
    st.plotly_chart(fig)

    # Efficiency vs Quality: Industry Comparison
    st.subheader("Efficiency vs Quality: Industry Comparison")

    industry_manual_speed = 30  # 100 annotations/hour
    industry_model_speed = 30 * 1.5  # 150 annotations/hour (50% increase)
    # Create a DataFrame for the comparison
    industry_comparison = pd.DataFrame(
        {
            "Labeling_Method": ["Manual", "Model-Assisted"],
            "Efficiency": [
                industry_manual_speed,
                industry_model_speed,
            ],  # 100 annotations/hour for manual, 150 for model-assisted (50% increase)
            "Quality": [
                95,
                97.85,
            ],  # 95% for manual, 97.85% for model-assisted (3% relative increase)
        }
    )

    # Create the scatter plot
    fig = px.scatter(
        industry_comparison,
        x="Efficiency",
        y="Quality",
        color="Labeling_Method",
        size=[40, 40],  # Make both points the same size
        labels={
            "Efficiency": "Efficiency (Annotations/Hour)",
            "Quality": "Quality (%)",
        },
        title="Efficiency vs Quality: Industry Standard",
        text="Labeling_Method",  # Add labels to the points
    )

    # Customize the layout
    fig.update_traces(textposition="top center")
    fig.update_layout(
        xaxis_range=[0, 60],
        yaxis_range=[90, 100],
        xaxis_title="Efficiency (Annotations/Hour)",
        yaxis_title="Quality (%)",
        legend_title="Labeling Method",
    )

    # Display the chart
    st.plotly_chart(fig)

    # Add explanation
    st.write(
        f"""
    This chart compares the efficiency and quality of manual labeling versus model-assisted labeling based on industry standards:

    - **Manual Labeling**: On average, human labelers can annotate about {industry_manual_speed} items per hour with a 95% accuracy rate.
    - **Model-Assisted Labeling**: With AI assistance, labelers can annotate approximately {industry_model_speed} items per hour (a 50% increase) 
        while achieving a 97.85% accuracy rate (a 3% relative increase).

    This visualization demonstrates that model-assisted labeling not only significantly increases efficiency but also improves the overall quality of annotations.
    """
    )

    # Key Insights
    st.subheader("Key Insights on Model-Assisted Labeling")
    st.write(
        f"""
    - Model-Assisted Labeling has reduced the total labeling time by {time_savings:.1f}%.
    - The average quality of annotations has improved by {(model_quality - manual_quality) / manual_quality:.1%}.
    - The error rate has been reduced by {error_reduction:.1f}%, significantly improving labeling accuracy.
    - Labeling speed has increased by {(model_speed - manual_speed) / manual_speed:.1%} when using Model-Assisted Labeling.
    - The efficiency gains and error rate reductions are consistent across different label types and concepts.
    - Model-Assisted Labeling shows a steady improvement in efficiency and accuracy over time, suggesting ongoing learning and adaptation.
    """
    )

    # Recommendation
    st.info(
        """
    **Recommendation**: Based on these insights, we recommend:
    1. Implementing Model-Assisted Labeling across all compatible data types and concepts.
    2. Continuously fine-tuning the assisting models to further improve efficiency, quality, and reduce error rates.
    3. Providing training to labelers on effectively using and validating model-assisted annotations.
    4. Regularly monitoring and comparing the performance of Model-Assisted vs Manual Labeling to ensure sustained benefits.
    5. Investing in AI-assisted labeling tools and workflows to stay competitive with industry standards and minimize errors.
    """
    )
# Footer
st.sidebar.markdown("---")
st.sidebar.write("© Clarifai - Labeling Quality Dashboard")
st.sidebar.write("Version 1.0")
