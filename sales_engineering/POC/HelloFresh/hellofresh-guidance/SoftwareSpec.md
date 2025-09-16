Program Specification: AI Brand Compliance Chatbot (Version 5.0 - HelloFresh Production)
This document outlines the requirements for a complete Streamlit application that functions as an AI-powered Brand Compliance Specialist for HelloFresh. The system has been fully implemented with enhanced JSON processing, deterministic predictions, and comprehensive brand validation.

Phase 1: Core Functionality & Statistics Dashboard ✅ COMPLETED
This phase focused on delivering the essential analysis engine, data persistence, and a historical dashboard.

1. Project Overview

Built an interactive web app to upload multiple images or a multi-page PDF.

The app calls user-selected LLMs (via Clarifai API) to analyze HelloFresh logo usage against brand guidelines.

It logs all analysis activities to a local database.

A dedicated statistics page presents historical data on usage, violations, and performance.

Enhanced with simplified JSON format, deterministic predictions (temperature=0), and improved brand rule accuracy.

2. Core Technologies & Services

Programming Language: Python 3.12+

Web Framework: Streamlit

AI Model Provider: Clarifai

AI Models: Gemini 2.5 Pro, Gemini 1.5 Pro, GPT-4o, MM Poly 8B

PDF Generation: fpdf2 / WeasyPrint

PDF Processing: PyMuPDF (fitz)

Data Persistence: SQLite3 with enhanced logging

Data Visualization: Plotly

API Key Management: Streamlit Secrets (st.secrets)

Configuration Management: TOML-based with unified model prompts

3. User Interface & Workflow

Sidebar Navigation: Radio button group to switch between:

Compliance Analysis

Statistics Dashboard

Sidebar Configuration: Dropdown menu to select AI Model for analysis.

Page 1: Compliance Analysis:

Multi-file uploader for images and PDFs.

Real-time analysis with deterministic results (temperature=0).

Enhanced violation display with separate description and recommendation fields.

Results displayed in expandable sections for each asset, with tabs for "Summary" and "Raw JSON Output."

Enhanced summary display with proper violation indentation and separate recommendations.

Download button for consolidated PDF report generation.

Page 2: Statistics Dashboard:

Key metric cards: Total Requests, Assets Analyzed, Compliance Rate, Avg. Response Time.

Token usage breakdown with interactive charts.

Bar chart for "Most Common HelloFresh Brand Guideline Violations."

Line chart for "Requests Over Time" with trend analysis.

Searchable dataframe with recent analysis records.

4. Backend Logic & API Integration

Database Setup: SQLite database with analysis_log and violations_log tables for comprehensive tracking.

Enhanced Input Processing: Handles images directly and extracts pages from PDFs with improved error handling.

Deterministic API Calls: All models configured with temperature=0.0 for consistent, reproducible results.

Unified Configuration: All model prompts centralized in config.toml with HelloFresh-specific brand guidelines.

Automated Logging: Performance metrics logged to analysis_log and violations to violations_log after each analysis.

Statistics Aggregation: Real-time SQL queries for dashboard metrics and visualizations.

Enhanced JSON Processing: Robust parsing with format detection for both simplified and legacy JSON structures.

5. HelloFresh Brand Guidelines Implemented

Logo Integrity: HelloFresh logo must not be stretched, rotated, recolored, or modified.

Brand Name Spelling: Accepts both "HelloFresh" (one word) and "HELLO FRESH" (two words, all caps).

Packaging Design: Official HelloFresh branding including delivery boxes, product packaging, and branded materials with correct green color scheme.

Text Legibility: All text clearly legible with sufficient size and contrast.

Food Presentation: All food depicted must be aesthetically pleasing, well-lit, and appetizing.

Brand Prominence: HelloFresh logo must be clearly visible and prominent.

Offer Disclaimer Pairing: All offers paired with legally required disclaimer text including specific requirements for different offer types.

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

No Logo Detected: Implement a friendly message ("✅ All clear! I didn't find a HelloFresh logo in this image...") if no logos are found.

API Failures: Provide a user-friendly message ("Uh oh! The AI analyst seems to be on a coffee break...") instead of a technical error if the API call fails.

Insightful Statistics Dashboard:

Contextual Suggestions: On the statistics page, next to the "Most Common Violations" chart, add a small, AI-generated section titled "What This Means." This will provide a brief, actionable insight based on the data (e.g., suggesting a training refresher on the most commonly violated rule).