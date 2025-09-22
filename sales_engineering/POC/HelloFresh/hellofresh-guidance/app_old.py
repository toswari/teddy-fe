import streamlit as st
import pandas as pd
import time
import base64
from datetime import datetime
from database import init_db, log_analysis, log_violation, get_statistics, get_recent_analysis, get_common_violations, get_compliance_trend
from clarifai_utils import analyze_images_batch, validate_batch_size, test_api_connection
from utils import extract_images_from_pdf, generate_report
from config_loader import get_available_models, get_model_config
from pdf_report_generator import generate_compliance_report
from weasyprint_report_generator import generate_compliance_report_weasyprint
from hellofresh_branded_report_generator import generate_hellofresh_compliance_report
import plotly.express as px
import plotly.graph_objects as go

# --- Page Configuration ---
st.set_page_config(
    page_title="AI Brand Compliance Specialist",
    page_icon="✅",
    layout="wide",
)

# --- Database Initialization ---
init_db()

# --- Main Application ---
def main():
    st.title("🎯 AI Brand Compliance Specialist")
    st.markdown("*Powered by Clarifai AI • Ensuring HelloFresh Brand Guidelines Compliance*")

    # --- Sidebar ---
    with st.sidebar:
        st.header("🔧 Configuration")
        
        # Test API connection
        if test_api_connection():
            st.success("✅ API Connected")
        else:
            st.error("❌ API Connection Failed")
            st.warning("Please check your CLARIFAI_PAT in secrets.toml")
        
        st.divider()
        
        # Page selection
        page = st.radio("Select Page", ["Compliance Analysis", "Statistics Dashboard"])
        
        # Model selection from config
        try:
            available_models = get_available_models()
            if available_models:
                model_display_names = list(available_models.values())
                model_ids = list(available_models.keys())
                
                selected_display_name = st.selectbox(
                    "🤖 Select AI Model",
                    model_display_names,
                    help="Choose the AI model for analysis"
                )
                
                # Get the corresponding model_id
                model_id = model_ids[model_display_names.index(selected_display_name)]
            else:
                st.error("No models configured")
                model_id = None
        except Exception as e:
            st.error(f"Configuration error: {e}")
            model_id = None

    # --- Page Content ---
    if page == "Compliance Analysis":
        compliance_analysis_page(model_id)
    elif page == "Statistics Dashboard":
        statistics_dashboard_page()

def compliance_analysis_page(model_id):
    st.header("📋 Brand Compliance Analysis")
    
    if not model_id:
        st.error("Please configure models in config.toml")
        return
    
    # Show model info
    try:
        model_config = get_model_config(model_id)
        with st.expander("ℹ️ Model Information"):
            st.write(f"**Model:** {model_config['model_name']}")
            st.write(f"**URL:** {model_config['model_url']}")
    except Exception as e:
        st.warning(f"Could not load model configuration: {e}")
    
    # File upload
    uploaded_files = st.file_uploader(
        "📎 Upload images or a multi-page PDF", 
        type=["png", "jpg", "jpeg", "pdf"], 
        accept_multiple_files=True,
        help="Supported formats: PNG, JPG, JPEG, PDF"
    )

    if st.button("🔍 Analyze Compliance", type="primary", use_container_width=True):
        if uploaded_files:
            # Collect all images for batch processing
            all_images = []
            file_info = []  # Track filename and page info for each image
            
            status_text = st.empty()
            status_text.text("📁 Collecting images for batch processing...")
            
            for uploaded_file in uploaded_files:
                if uploaded_file.type == "application/pdf":
                    status_text.text(f"Extracting pages from {uploaded_file.name}...")
                    images = extract_images_from_pdf(uploaded_file.getvalue())
                    
                    for i, image_bytes in enumerate(images):
                        page_num = i + 1
                        all_images.append(image_bytes)
                        file_info.append({
                            'filename': uploaded_file.name,
                            'page_number': page_num,
                            'image_bytes': image_bytes
                        })
                else:
                    all_images.append(uploaded_file.getvalue())
                    file_info.append({
                        'filename': uploaded_file.name,
                        'page_number': None,
                        'image_bytes': uploaded_file.getvalue()
                    })
            
            # Validate batch size
            try:
                validate_batch_size(all_images)
                total_size = sum(len(img) for img in all_images)
                status_text.success(f"✅ Batch validated: {len(all_images)} images, {total_size / (1024*1024):.1f} MB total")
            except ValueError as e:
                st.error(f"❌ Batch validation failed: {e}")
                st.info("💡 Try uploading fewer images or smaller files (max 128 images, 128 MB total)")
                return
            
            # Process batch
            with st.spinner(f"🚀 Processing {len(all_images)} images using batch API..."):
                start_time = time.time()
                
                try:
                    # Use batch processing
                    batch_results = analyze_images_batch(all_images, model_id)
                    end_time = time.time()
                    
                    processing_time = end_time - start_time
                    avg_time_per_image = processing_time / len(all_images)
                    
                    st.success(f"✅ Batch processing completed in {processing_time:.1f}s (avg {avg_time_per_image:.1f}s per image)")
                    
                    # Convert batch results to the expected format
                    all_results = []
                    for i, batch_result in enumerate(batch_results):
                        if i < len(file_info):  # Safety check
                            file_data = file_info[i]
                            
                            # Log to database
                            compliance_status = batch_result['json_output'].get('compliance_status', 'Error')
                            analysis_id = log_analysis(
                                filename=file_data['filename'],
                                page_number=file_data['page_number'],
                                model_id=model_id,
                                response_time=processing_time / len(all_images),  # Estimate per image
                                input_tokens=batch_result['input_tokens'],
                                output_tokens=batch_result['output_tokens'],
                                compliance_status=compliance_status
                            )
                            
                            # Log violations
                            for violation in batch_result['violations']:
                                log_violation(
                                    analysis_id=analysis_id,
                                    rule_violated=violation.get('rule_violated', 'Unknown'),
                                    description=violation.get('description', '')
                                )
                            
                            # Convert to expected format
                            result = {
                                "filename": file_data['filename'],
                                "page_number": file_data['page_number'],
                                "image_bytes": file_data['image_bytes'],
                                "summary": batch_result['summary'],
                                "json_output": batch_result['json_output'],
                                "compliance_status": compliance_status,
                                "violations": batch_result['violations'],
                                "response_time": processing_time / len(all_images)
                            }
                            all_results.append(result)
                    
                except Exception as e:
                    st.error(f"❌ Batch processing failed: {str(e)}")
                    st.info("🔄 This might be due to API limits or connectivity issues. Please try with fewer images.")
                    return
            
            # Filter out any None results
            all_results = [r for r in all_results if r is not None]
            
            # Debug: Check the structure of results
            if all_results:
                st.write(f"Debug: First result keys: {list(all_results[0].keys()) if all_results[0] else 'None'}")
            
            # Display results
            st.success(f"✅ Analyzed {len(all_results)} assets successfully!")
            
            # Summary metrics with safe access and error handling
            try:
                col1, col2, col3 = st.columns(3)
                compliant_count = sum(1 for r in all_results if r and r.get('compliance_status') == 'Compliant')
                non_compliant_count = sum(1 for r in all_results if r and r.get('compliance_status') == 'Non-Compliant')
                no_logo_count = sum(1 for r in all_results if r and r.get('compliance_status') == 'No Logo Found')
                
                col1.metric("✅ Compliant", compliant_count)
                col2.metric("❌ Non-Compliant", non_compliant_count)
                col3.metric("🔍 No Logo Found", no_logo_count)
            except Exception as e:
                st.error(f"Error calculating summary metrics: {e}")
                st.write(f"Debug: all_results length: {len(all_results)}")
                st.write(f"Debug: all_results content: {all_results[:3] if all_results else 'Empty'}")

            # Store results in session state for PDF generation and persistence
            st.session_state.analysis_results = all_results
            st.session_state.current_model_id = model_id
            
            # Show the PDF generation and download section
            show_pdf_generation_section()
            
            # PDF Report Generation Section
            st.markdown("---")
            st.markdown("### 📄 Generate Professional Reports")
            
            st.markdown("Choose your preferred report format:")
            
            # Create three columns for different report options
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**🎨 Enhanced Report with Emojis**")
                st.markdown("Modern design with emoji support using WeasyPrint")
                if st.button("🎨 Generate Enhanced Report", type="primary", use_container_width=True):
                    try:
                        with st.spinner("Generating enhanced PDF report with emoji support..."):
                            # Prepare data for PDF generation
                            pdf_data = prepare_pdf_data(all_results)
                            
                            # Generate PDF using WeasyPrint with emoji support
                            pdf_bytes = generate_compliance_report_weasyprint(
                                pdf_data, 
                                {
                                    'generated_at': datetime.now(),
                                    'model_used': model_id or 'AI Model',
                                    'total_assets': len(all_results),
                                    'emoji_support': True,
                                    'professional_styling': True
                                }
                            )
                            
                            # Store in session state
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.session_state.enhanced_pdf = pdf_bytes
                            st.session_state.enhanced_filename = f"Enhanced_Report_Emoji_{timestamp}.pdf"
                            
                            st.success(f"✅ Enhanced report generated! ({len(pdf_bytes):,} bytes)")
                            
                    except Exception as e:
                        st.error(f"❌ Error generating enhanced PDF: {str(e)}")
                        st.exception(e)
            
            with col2:
                st.markdown("**📋 Standard Report**")
                st.markdown("Classic format for formal documentation")
                if st.button("� Generate Standard Report", type="secondary", use_container_width=True):
                    try:
                        with st.spinner("Generating standard PDF report..."):
                            # Prepare data for PDF generation
                            pdf_data = prepare_pdf_data(all_results)
                            
                            # Generate PDF using original generator
                            pdf_bytes = generate_compliance_report(
                                pdf_data, 
                                {
                                    'generated_at': datetime.now(),
                                    'model_used': model_id or 'AI Model',
                                    'total_assets': len(all_results)
                                }
                            )
                            
                            # Store in session state
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            st.session_state.standard_pdf = pdf_bytes
                            st.session_state.standard_filename = f"Standard_Report_{timestamp}.pdf"
                            
                            st.success(f"✅ Standard report generated! ({len(pdf_bytes):,} bytes)")
                            
                    except Exception as e:
                        st.error(f"❌ Error generating standard PDF: {str(e)}")
                        st.exception(e)
            
            with col3:
                st.markdown("**📊 Both Formats**")
                st.markdown("Generate both report types")
                if st.button("� Generate Both Reports", use_container_width=True):
                    try:
                        with st.spinner("Generating both report formats..."):
                            # Prepare data for PDF generation
                            pdf_data = prepare_pdf_data(all_results)
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            
                            # Generate both reports
                            standard_pdf = generate_compliance_report(pdf_data, {
                                'generated_at': datetime.now(),
                                'model_used': model_id or 'AI Model',
                                'total_assets': len(all_results)
                            })
                            
                            enhanced_pdf = generate_compliance_report_weasyprint(pdf_data, {
                                'generated_at': datetime.now(),
                                'model_used': model_id or 'AI Model',
                                'total_assets': len(all_results),
                                'emoji_support': True,
                                'professional_styling': True
                            })
                            
                            # Store both in session state
                            st.session_state.standard_pdf = standard_pdf
                            st.session_state.standard_filename = f"Standard_{timestamp}.pdf"
                            st.session_state.enhanced_pdf = enhanced_pdf
                            st.session_state.enhanced_filename = f"Enhanced_{timestamp}.pdf"
                            
                            st.success(f"✅ Both reports ready! Standard: {len(standard_pdf):,} bytes | Enhanced: {len(enhanced_pdf):,} bytes")
                            
                    except Exception as e:
                        st.error(f"❌ Error generating reports: {str(e)}")
                        st.exception(e)
            
            # Download section - only show if PDFs are generated
            if hasattr(st.session_state, 'enhanced_pdf') or hasattr(st.session_state, 'standard_pdf'):
                st.markdown("### 📥 Download Generated Reports")
                
                download_col1, download_col2 = st.columns(2)
                
                with download_col1:
                    if hasattr(st.session_state, 'enhanced_pdf'):
                        st.download_button(
                            label="📄 Download Enhanced Report",
                            data=st.session_state.enhanced_pdf,
                            file_name=st.session_state.enhanced_filename,
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )
                
                with download_col2:
                    if hasattr(st.session_state, 'standard_pdf'):
                        st.download_button(
                            label="📄 Download Standard Report",
                            data=st.session_state.standard_pdf,
                            file_name=st.session_state.standard_filename,
                            mime="application/pdf",
                            type="secondary",
                            use_container_width=True
                        )
            
            # Detailed Results Section
            st.markdown("### 📋 Detailed Analysis Results")
            
            for result in all_results:
                if not result:  # Skip any None results
                    continue
                    
                asset_display_name = result.get('filename', 'Unknown File')
                if result.get('page_number'):
                    asset_display_name += f" (Page {result['page_number']})"
                
                # Status emoji
                status_emoji = {
                    'Compliant': '✅',
                    'Non-Compliant': '❌',
                    'No Logo Found': '🔍',
                    'Error': '⚠️'
                }.get(result.get('compliance_status', 'Unknown'), '❓')
                
                with st.expander(f"{status_emoji} {asset_display_name} - {result.get('compliance_status', 'Unknown')}"):
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        if result.get('image_bytes'):
                            st.image(result['image_bytes'], caption="Analyzed Image", use_container_width=True)
                        else:
                            st.write("Image not available")
                    
                    with col2:
                        tab1, tab2 = st.tabs(["📝 Summary", "🔧 Technical Details"])
                        
                        with tab1:
                            st.write("**Analysis Summary:**")
                            st.write(result['summary'])
                            
                            if result['violations']:
                                st.write("**Violations Found:**")
                                for violation in result['violations']:
                                    st.warning(f"**{violation['rule_violated']}**: {violation['description']}")
                            
                            if 'recommendations' in result['json_output']:
                                st.write("**Recommendations:**")
                                for rec in result['json_output']['recommendations']:
                                    st.info(f"💡 {rec}")
                        
                        with tab2:
                            st.json(result['json_output'])
            
            # PDF report generation
            if all_results:
                with st.spinner("Generating PDF report..."):
                    pdf_bytes = generate_report(all_results)
                
                st.download_button(
                    label="📄 Download Full Report (PDF)",
                    data=pdf_bytes,
                    file_name=f"compliance_report_{int(time.time())}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

        else:
            st.warning("⚠️ Please upload at least one file.")


def statistics_dashboard_page():
    st.header("📊 Statistics Dashboard")
    
    # Get statistics
    try:
        stats = get_statistics()
    except Exception as e:
        st.error(f"Error loading statistics: {e}")
        return
    
    # Key metrics
    st.subheader("📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Requests", 
            stats['total_requests'],
            help="Total number of analysis requests made"
        )
    
    with col2:
        st.metric(
            "Assets Analyzed", 
            stats['total_assets'],
            help="Total number of individual assets processed"
        )
    
    with col3:
        st.metric(
            "Compliance Rate", 
            f"{stats['compliance_rate']:.1f}%",
            help="Percentage of assets that are compliant"
        )
    
    with col4:
        st.metric(
            "Avg. Response Time", 
            f"{stats['avg_response_time']:.2f}s",
            help="Average time taken for analysis"
        )

    # Token usage
    st.subheader("🔤 Token Usage Analysis")
    if stats['tokens_by_model']:
        token_df = pd.DataFrame(stats['tokens_by_model'])
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Pie chart for total token usage
            fig_pie = px.pie(
                token_df, 
                values='total_tokens', 
                names='model_id', 
                title='Token Distribution by Model'
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            # Bar chart for input vs output tokens
            fig_bar = px.bar(
                token_df, 
                x='model_id', 
                y=['input_tokens', 'output_tokens'],
                title='Input vs Output Tokens by Model',
                barmode='stack'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("No token usage data available yet.")

    # Compliance trend
    st.subheader("📅 Compliance Trend (Last 30 Days)")
    try:
        trend_data = get_compliance_trend(30)
        if trend_data:
            trend_df = pd.DataFrame(trend_data)
            
            fig_trend = go.Figure()
            
            # Add compliance rate line
            fig_trend.add_trace(go.Scatter(
                x=trend_df['date'],
                y=trend_df['compliance_rate'],
                mode='lines+markers',
                name='Compliance Rate (%)',
                line=dict(color='green', width=3)
            ))
            
            # Add total analyses bar
            fig_trend.add_trace(go.Bar(
                x=trend_df['date'],
                y=trend_df['total_analyses'],
                name='Total Analyses',
                yaxis='y2',
                opacity=0.6,
                marker_color='lightblue'
            ))
            
            fig_trend.update_layout(
                title='Compliance Rate and Analysis Volume Over Time',
                xaxis_title='Date',
                yaxis=dict(title='Compliance Rate (%)', side='left'),
                yaxis2=dict(title='Number of Analyses', side='right', overlaying='y'),
                hovermode='x unified'
            )
            
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No trend data available yet.")
    except Exception as e:
        st.warning(f"Could not load trend data: {e}")

    # Most common violations
    st.subheader("⚠️ Most Common Brand Guideline Violations")
    try:
        violations_data = get_common_violations(10)
        if violations_data:
            violations_df = pd.DataFrame(violations_data)
            
            fig_violations = px.bar(
                violations_df, 
                x='count', 
                y='rule_violated',
                orientation='h',
                title='Top Brand Guideline Violations',
                color='count',
                color_continuous_scale='Reds'
            )
            fig_violations.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_violations, use_container_width=True)
            
            # AI-generated insights
            with st.expander("🤖 What This Means - AI Insights"):
                if violations_data:
                    top_violation = violations_data[0]['rule_violated']
                    violation_count = violations_data[0]['count']
                    
                    st.info(f"""
                    **Key Finding**: The most common violation is "{top_violation}" with {violation_count} occurrences.
                    
                    **Recommendations**:
                    - Consider providing additional training on {top_violation.lower()} guidelines
                    - Review assets that frequently violate this rule
                    - Update brand guidelines documentation if needed
                    - Implement preventive measures in the design workflow
                    """)
        else:
            st.info("No violation data available yet.")
    except Exception as e:
        st.warning(f"Could not load violations data: {e}")

    # Requests over time
    st.subheader("📊 Analysis Activity (Last 30 Days)")
    if stats['requests_over_time']:
        requests_df = pd.DataFrame(stats['requests_over_time'])
        
        fig_requests = px.line(
            requests_df, 
            x='date', 
            y='count',
            title='Daily Analysis Requests',
            markers=True
        )
        fig_requests.update_traces(line_color='blue')
        st.plotly_chart(fig_requests, use_container_width=True)
    else:
        st.info("No recent activity data available.")

    # Recent analysis table
    st.subheader("📋 Recent Analysis Records")
    try:
        recent_data = get_recent_analysis(50)
        if recent_data:
            recent_df = pd.DataFrame(recent_data)
            
            # Format the dataframe for better display
            recent_df['timestamp'] = pd.to_datetime(recent_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')
            recent_df['response_time_seconds'] = recent_df['response_time_seconds'].round(2)
            
            # Add status emoji
            status_map = {
                'Compliant': '✅',
                'Non-Compliant': '❌',
                'No Logo Found': '🔍',
                'Error': '⚠️'
            }
            recent_df['status_display'] = recent_df['compliance_status'].map(status_map) + ' ' + recent_df['compliance_status']
            
            # Display with filters
            status_filter = st.multiselect(
                "Filter by Status",
                options=recent_df['compliance_status'].unique(),
                default=recent_df['compliance_status'].unique()
            )
            
            filtered_df = recent_df[recent_df['compliance_status'].isin(status_filter)]
            
            # Display columns
            display_columns = [
                'timestamp', 'filename', 'page_number', 'model_id', 
                'status_display', 'response_time_seconds', 'input_tokens', 'output_tokens'
            ]
            
            st.dataframe(
                filtered_df[display_columns],
                use_container_width=True,
                column_config={
                    'timestamp': 'Timestamp',
                    'filename': 'File Name',
                    'page_number': 'Page #',
                    'model_id': 'Model',
                    'status_display': 'Status',
                    'response_time_seconds': 'Response Time (s)',
                    'input_tokens': 'Input Tokens',
                    'output_tokens': 'Output Tokens'
                }
            )
        else:
            st.info("No recent analysis data available.")
    except Exception as e:
        st.warning(f"Could not load recent analysis data: {e}")


def prepare_pdf_data(analysis_results):
    """
    Prepare analysis results data for PDF generation.
    
    Args:
        analysis_results: List of analysis result dictionaries from the app
        
    Returns:
        List of formatted data for PDF generation
    """
    pdf_data = []
    
    for result in analysis_results:
        if not result:
            continue
            
        # Extract filename with page number if applicable
        filename = result.get('filename', 'Unknown File')
        if result.get('page_number'):
            filename += f" - Page {result['page_number']}"
        
        # Prepare image data for PDF
        image_data = None
        if result.get('image_bytes'):
            # Convert image bytes to base64 for PDF processing
            try:
                image_data = base64.b64encode(result['image_bytes']).decode('utf-8')
            except Exception as e:
                print(f"Error encoding image for PDF: {e}")
        
        # Format the result for PDF generation
        pdf_result = {
            'filename': filename,
            'image_data': image_data,
            'json_output': result.get('json_output', {}),
            'compliance_status': result.get('compliance_status', 'Unknown'),
            'summary': result.get('summary', 'No summary available'),
            'input_tokens': result.get('input_tokens', 0),
            'output_tokens': result.get('output_tokens', 0),
            'violations': result.get('violations', [])
        }
        
        pdf_data.append(pdf_result)
    
    return pdf_data


if __name__ == "__main__":
    main()
