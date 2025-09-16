Detailed Design Specification: AI Brand Compliance Chatbot
Version: 4.2 (Final)
Date: September 15, 2025

1. Executive Summary
This document outlines the detailed design and architecture for the AI Brand Compliance Chatbot, a Streamlit web application. The application is designed to function as an automated Brand Compliance Specialist, analyzing visual assets (images and PDFs) to ensure adherence to HelloFresh's corporate branding guidelines.

The system will leverage a user-selectable, powerful multimodal Large Language Model (LLM) via the Clarifai API, guided by a sophisticated, configurable prompt. All analysis activities will be logged to a local SQLite3 database to power a historical statistics dashboard, providing actionable insights into compliance trends and common errors. The project will be developed in two distinct phases: Phase 1 focuses on core functionality, while Phase 2 enhances the user experience with interactive and intuitive features.

2. System Architecture
The application follows a modular architecture composed of a Streamlit frontend, a Python backend, an external API for AI processing, and a local file-based database for data persistence.

2.1. Architectural Diagram
2.2. Component Flow
Configuration: On startup, the Python backend loads credentials and structured prompts from the config.toml file.

User Interaction: The user interacts with the Streamlit frontend, selecting an AI model and uploading assets.

Backend Processing: The backend processes the files, sending a request for each image to the Clarifai API. This request combines the image data with the appropriate prompt text loaded from the config file.

AI Analysis: The Clarifai API processes the request using the specified LLM and returns a structured JSON response as dictated by the prompt.

Data Persistence: The backend logs the results, metrics, and any violations from the API response into the local compliance_data.db SQLite database.

Presentation: Results are displayed on the frontend. The Statistics Dashboard queries the SQLite database to generate and display historical analytics.

3. Configuration Management
A central config.toml file will be used to manage all external settings, ensuring that credentials, model IDs, and prompts can be modified without changing the source code.

File: config.toml

# AI Brand Compliance Chatbot Configuration

[clarifai]
api_key = "YOUR_CLARIFAI_API_KEY_HERE"
user_id = "YOUR_CLARIFAI_USER_ID"
app_id = "YOUR_CLARIFAI_APP_ID"

# -----------------------------------------------------------------------------
# PROMPT DEFINITIONS
# The application will populate the model selection UI from this section.
# The section key (e.g., "gemini-2.5-pro") is the model_id sent to the API.
# -----------------------------------------------------------------------------
[prompts]

    [prompts."gemini-2.5-pro"]
    model_name = "Gemini 2.5 Pro" # User-facing name in the dropdown
    prompt_text = """
    Persona: You are a meticulous Brand Compliance Specialist AI...
    (The full, detailed prompt as previously defined goes here)
    ...5.1. Logo Count: A single piece of creative should not be cluttered...
    """

    [prompts."gpt-4o"]
    model_name = "GPT-4o"
    prompt_text = """
    # This is a placeholder for a prompt optimized for GPT-4o.
    # It can be a copy of the Gemini prompt or a tuned version.
    Persona: You are a meticulous Brand Compliance Specialist AI...
    """

4. Database Design
Technology Decision: The application will use SQLite3 via Python's built-in sqlite3 library.

Database File: compliance_data.db (will be created automatically in the project's root directory).

4.1. Schema Definition
Table 1: analysis_log

Stores a record for each asset (image or PDF page) analyzed.

Columns:

id (INTEGER, PRIMARY KEY, AUTOINCREMENT)

timestamp (TIMESTAMP, NOT NULL)

filename (TEXT, NOT NULL)

page_number (INTEGER, NULL) - For multi-page PDFs

model_id (TEXT, NOT NULL)

response_time_seconds (REAL, NOT NULL)

input_tokens (INTEGER)

output_tokens (INTEGER)

compliance_status (TEXT, NOT NULL) - e.g., "Compliant", "Non-compliant"

Table 2: violations_log

Stores a record for each specific brand guideline violation found.

Columns:

id (INTEGER, PRIMARY KEY, AUTOINCREMENT)

analysis_id (INTEGER, NOT NULL, FOREIGN KEY REFERENCES analysis_log(id))

rule_violated (TEXT, NOT NULL) - e.g., "2.3. Alignment"

description (TEXT, NOT NULL) - The violation detail from the AI's response.

5. Component Breakdown & Responsibilities
The backend will be organized into distinct Python modules for clarity and maintainability.

main_app.py: The entry point and main Streamlit script.

Responsibilities: Renders all UI components, manages application state, handles user input, and orchestrates the workflow by calling other modules.

config_loader.py:

Responsibilities: Reads and parses the config.toml file on startup, returning a clean dictionary of settings.

api_handler.py:

Responsibilities: Manages all communication with the Clarifai API. Contains the function analyze_asset() which constructs the payload (prompt + image), makes the API call, and handles responses and network errors.

db_handler.py:

Responsibilities: Manages all database interactions (CRUD operations). Initializes the DB, creates tables, logs new analysis records and violations, and contains functions to query aggregated data for the statistics dashboard.

ui_components.py (Phase 2):

Responsibilities: Contains functions for rendering complex UI elements, such as drawing bounding boxes on images or generating the "Example Gallery."

6. Phased Rollout Plan
Phase 1: Core Functionality & Statistics (MVP)
This phase delivers a fully functional analysis tool with a robust backend.

Features:

UI: Two-page layout (Analysis & Statistics) with sidebar navigation.

Configuration: Model selection dropdown populated from config.toml.

Analysis Engine:

Multi-file uploader for images and PDFs.

Backend logic to iterate through files/pages and call the selected Clarifai model with the correct prompt.

Results displayed in expanders with "Summary" and "JSON" tabs.

Reporting: Downloadable consolidated PDF report of the current session's analysis.

Database: Full implementation of the SQLite database for logging every transaction.

Statistics Dashboard: All specified metrics, charts (violations, token usage, requests over time), and a searchable data table of past analyses.

Phase 2: User Experience & Friendliness Enhancements
This phase refines the application, making it more intuitive, interactive, and insightful.

Features:

Onboarding: An "Example Gallery" on the main page to demonstrate functionality instantly.

Visual Feedback: In the analysis results, the user's image will be displayed with color-coded bounding boxes drawn around detected logos to pinpoint issues.

Conversational UI: Recommendation text will be converted from technical jargon to friendly, actionable advice.

UI/UX Polish:

A real-time st.progress bar for multi-file uploads.

A "Start New Analysis" button to clear the session state.

Graceful handling of edge cases (e.g., no logo found, API errors) with user-friendly messages.

Enhanced Statistics: The dashboard will include an AI-generated "What This Means" section, providing contextual insights based on the violation data.

7. Error Handling & Edge Cases
The application will be designed to handle the following scenarios gracefully:

Invalid File Type: The file uploader will be restricted to png, jpg, jpeg, and pdf.

API Failure: If a call to the Clarifai API fails (e.g., network error, invalid key), a user-friendly error message will be displayed in the UI instead of a technical traceback.

No Logo Detected: If the AI analyzes an image and finds no logo, the status will be "No Logo Found" and a helpful message will be displayed.

Corrupt File: If an uploaded PDF or image cannot be processed, a skippable error message for that specific file will be shown, allowing the rest of the batch to be analyzed.