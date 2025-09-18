Program Specification: AI Brand Compliance Chatbot (Version 4.0 - Phased)
This document outlines the requirements for creating a multi-faceted Streamlit application that functions as an AI-powered Brand Compliance Specialist. The project is divided into two phases to manage development and feature rollout.

Phase 1: Core Functionality & Statistics Dashboard
This phase focuses on delivering the essential analysis engine, data persistence, and a historical dashboard.

1. Project Overview (Phase 1)

Build an interactive web app to upload multiple images or a multi-page PDF.

The app will call a user-selected LLM (via Clarifai API) to analyze Kia logo usage against brand guidelines.

It will log all analysis activities to a local database.

A dedicated statistics page will present historical data on usage, violations, and performance.

2. Core Technologies & Services

Programming Language: Python 3.9+

Web Framework: Streamlit

AI Model Provider: Clarifai

AI Models: Gemini 2.5 Pro, GPT-4o, Claude 3 Opus, etc.

PDF Generation: fpdf2

PDF Processing: PyMuPDF (or fitz)

Data Persistence: Python's built-in sqlite3

Data Visualization: Plotly or Altair

API Key Management: Streamlit Secrets (st.secrets)

3. User Interface & Workflow (Phase 1)

Sidebar Navigation: A radio button group to switch between:

Compliance Analysis

Statistics Dashboard

Sidebar Configuration: A dropdown menu to select the AI Model for analysis.

Page 1: Compliance Analysis:

Multi-file uploader for images and PDFs.

"Analyze Compliance" button to trigger the workflow.

Results displayed in st.expander for each asset, with tabs for "Layman's Summary" and "Full JSON Output."

Download button for a consolidated PDF report.

Page 2: Statistics Dashboard:

Key metric cards: Total Requests, Assets Analyzed, Compliance Rate, Avg. Response Time.

Token usage breakdown (metrics and pie chart).

Bar chart for "Most Common Brand Guideline Violations."

Line chart for "Requests Over Time."

Searchable dataframe with recent analysis records.

4. Backend Logic & API Integration (Phase 1)

Database Setup: Initialize a local SQLite database with analysis_log and violations_log tables.

Input Processing Loop: Iterate through uploaded files, handle images directly, and extract pages from PDFs to process as images.

Parameterized API Calls: The function calling the Clarifai API will use the model_id selected by the user.

Automated Logging: After each asset analysis, log performance metrics to analysis_log and any specific violations to violations_log.

Statistics Aggregation: When the statistics page is loaded, run SQL queries on the SQLite DB to calculate and aggregate data for the charts and metrics.

Phase 2: User Experience & Friendliness Enhancements
This phase focuses on making the application more intuitive, interactive, and insightful for the end-user.

1. Project Overview (Phase 2)

Improve the onboarding process with guided examples.

Make the feedback from the AI more visual and easier to understand.

Add quality-of-life UI improvements to reduce user friction.

Transform the statistics dashboard from a simple report into a strategic tool.

2. UI & Feature Enhancements (Phase 2)

Onboarding & Guidance:

Example Gallery: On the analysis page, add a "See How It Works" section with clickable thumbnails of pre-canned examples (compliant, non-compliant). Clicking an example will automatically run the analysis to demonstrate the tool's functionality.

Interactive Guideline Summary: Add an st.expander titled "Review the Brand Guidelines" containing a simplified, visual summary of the core rules.

Interactive & Visual Feedback:

Visualize Bounding Boxes: In the results for each image, use Pillow or OpenCV to draw bounding boxes directly onto the image. The annotated image will be displayed, with color-coded boxes (e.g., green for compliant, red for non-compliant) to highlight the AI's findings visually.

Human-Centric Language: Refine the backend logic to convert technical violation descriptions into conversational, encouraging, and actionable recommendations.

Quality of Life UI Improvements:

Smarter Progress Indicators: When processing multiple files, replace the st.spinner with an st.progress bar that updates in real-time to show progress (e.g., "Analyzing page 3 of 10...").

"Clear Session" Button: Add a "Start New Analysis" button to clear all uploaded files and previous results from the view, allowing users to easily start a new session.

Graceful Error Handling:

No Logo Detected: Implement a friendly message ("✅ All clear! I didn't find a Kia logo in this image...") if no logos are found.

API Failures: Provide a user-friendly message ("Uh oh! The AI analyst seems to be on a coffee break...") instead of a technical error if the API call fails.

Insightful Statistics Dashboard:

Contextual Suggestions: On the statistics page, next to the "Most Common Violations" chart, add a small, AI-generated section titled "What This Means." This will provide a brief, actionable insight based on the data (e.g., suggesting a training refresher on the most commonly violated rule).