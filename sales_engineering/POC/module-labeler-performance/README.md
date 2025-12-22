![Clarifai logo](https://www.clarifai.com/hs-fs/hubfs/logo/Clarifai/clarifai-740x150.png?width=240)

# Labeler Quality and Performance Dashboard

A comprehensive Streamlit dashboard for analyzing and comparing the performance and quality of manual vs. model-assisted data labeling. This tool helps teams quantify the impact of AI-assisted labeling on productivity, accuracy, and time savings.

## Overview

This dashboard provides real-time insights into labeling operations across multiple dimensions:
- **Quality Metrics**: Track accuracy, error rates, and quality scores
- **Performance Analytics**: Monitor labeling speed and throughput
- **Time Savings**: Calculate ROI from model-assisted labeling
- **Comparative Analysis**: Side-by-side comparison of manual vs. AI-assisted workflows
- **Multi-dimensional Filtering**: Analyze by date range, labeler, concept, and label type

## Features

### 📊 Two Analysis Views

#### 1. Manual Labeling Stats
- Individual labeler performance metrics
- Quality scores and error rates by labeler
- Annotations per hour analysis
- Temporal trends and patterns
- Concept-specific performance breakdown

#### 2. Model-Assisted Labeling
- Overall metrics comparison (Manual vs. Model-Assisted)
  - Total annotations with percentage change
  - Average quality score improvements
  - Error rate reductions
  - Speed improvements (ann/hour)
- Time savings calculations with ROI metrics
- Detailed performance charts and visualizations

### 🔍 Interactive Filters

- **Date Range Selector**: Analyze specific time periods
- **Labeler Selection**: Filter by individual team members
- **Concept Selection**: Focus on specific labeling concepts (HEMITT, HMMVW, LMTV, JLTV)
- **Label Type Selection**: Filter by data modality:
  - Electro-Optical (EO)
  - Full Motion Video (FMV)
  - Horizontal Motion Imagery (HMI)
  - Synthetic Aperture Radar (SAR)
  - Multi-Modal Data
  - Natural Language Processing (NLP)

### 📈 Key Metrics Tracked

- **Annotations**: Total volume and throughput
- **Quality Score**: Accuracy percentage (0-100%)
- **Error Rate**: Percentage of incorrect annotations
- **Labeling Speed**: Annotations per hour
- **Time Taken**: Total hours spent on labeling
- **Time Savings**: Percentage reduction with model assistance

### 📉 Visualizations

1. **Quality by Labeler**: Bar chart comparing quality scores
2. **Error Rate Analysis**: Visual comparison of error rates
3. **Annotations Distribution**: Volume analysis by labeler
4. **Speed Comparison**: Labeling speed metrics
5. **Time Savings**: ROI visualization for model-assisted labeling
6. **Temporal Trends**: Performance over time

## Installation

### Requirements

```bash
pip install -r requirements.txt
```

Required packages:
- `streamlit` - Web application framework
- `pandas` - Data manipulation and analysis
- `plotly` - Interactive visualizations
- `numpy` - Numerical computations

## Usage

### Running the Dashboard

```bash
streamlit run app.py
```

The dashboard will open in your browser at `http://localhost:8501`

### Sample Data

The app includes a sample data generator that creates realistic labeling performance data for demonstration purposes. In production, replace this with your actual labeling data source.

## Data Structure

The dashboard expects data in the following format:

```python
{
    "Date": datetime,
    "Labeler": str,
    "Concept": str,
    "Label_Type": str,
    "Labeling_Type": str,  # "Manual" or "Model-Assisted"
    "Annotations": int,
    "Quality": float,      # 0-100
    "Error_Rate": float,   # 0-100
    "Time_Taken": float,   # hours
}
```

## Configuration

### Customization Options

1. **Add New Concepts**: Edit the `concepts` list in app.py
2. **Add New Label Types**: Modify the `LABEL_TYPES` list
3. **Add Labelers**: Update the `labelers` list
4. **Adjust Date Range**: Modify the sample data generation date range

### Color Scheme

The dashboard uses Clarifai's brand colors with a blue accent (`#0069f9`) for multiselect options.

## Recent Updates

- ✅ Fixed date range selector IndexError
- ✅ Added safe division checks to prevent warnings
- ✅ Improved data validation for edge cases
- ✅ Removed dark mode for better visibility
- ✅ Enhanced error handling for empty datasets

## Use Cases

- **Team Performance Evaluation**: Compare individual labeler productivity and quality
- **ROI Analysis**: Quantify the business impact of model-assisted labeling
- **Quality Assurance**: Identify trends and areas for improvement
- **Resource Planning**: Optimize team allocation based on performance data
- **Process Improvement**: Track the effectiveness of training and new workflows

## Technical Details

### Architecture

- **Frontend**: Streamlit with Plotly visualizations
- **Data Processing**: Pandas for efficient data manipulation
- **Sample Data**: Generated using NumPy with realistic distributions
- **Styling**: Custom CSS for multiselect components

### Performance Metrics Calculation

- **Quality Score**: Based on annotation accuracy
- **Error Rate**: Percentage of annotations requiring correction
- **Speed**: Calculated as annotations per hour
- **Time Savings**: `(1 - model_assisted_time / manual_time) × 100%`

## License

Copyright © 2024 Clarifai, Inc. All rights reserved.

## Support

For questions or issues, please contact the Clarifai Field Engineering team or create an issue in the repository.
