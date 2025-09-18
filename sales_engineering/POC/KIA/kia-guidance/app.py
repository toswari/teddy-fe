import streamlit as st
import pandas as pd
import time
import base64
import json
from datetime import datetime
from database import init_db, log_analysis, log_violation, get_statistics, get_recent_analysis, get_common_violations, get_compliance_trend
from clarifai_utils import analyze_images_batch, validate_batch_size, test_api_connection
from utils import extract_images_from_pdf, generate_report
from config_loader import get_available_models, get_model_config
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
    st.markdown("*Powered by Clarifai AI • Ensuring Kia Brand Guidelines Compliance*")

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
        help="Supported formats: PNG, JPG, JPEG, PDF. Max 128 images, 128 MB total."
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
                # Store validation info for final summary (don't show success box yet)
                validation_info = {
                    'total_images': len(all_images),
                    'total_size_mb': total_size / (1024*1024)
                }
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
                    
                    # Store processing info for final summary (don't show success box yet)
                    processing_info = {
                        'processing_time': processing_time,
                        'avg_time_per_image': avg_time_per_image
                    }
                    
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
            
            # Display consolidated success message with all information
            st.success(f"""✅ **Analysis Complete!**
            
📊 **Batch:** {validation_info['total_images']} images, {validation_info['total_size_mb']:.1f} MB total
⏱️ **Processing:** {processing_info['processing_time']:.1f}s (avg {processing_info['avg_time_per_image']:.1f}s per image)
🎯 **Results:** {len(all_results)} assets analyzed successfully!""")
            
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

            # Store results in session state for persistence
            st.session_state.analysis_results = all_results
            st.session_state.current_model_id = model_id
            
            # Show detailed results
            show_detailed_results(all_results)

        else:
            st.warning("⚠️ Please upload at least one file.")


def _derive_recommendations_from_violations(violations):
    """Construct human-friendly recommendations from violation list if model did not supply any.
    Heuristic mapping based on rule keywords.
    """
    if not violations:
        return []
    suggestions = []
    for v in violations:
        rule = (v.get('rule_violated') or '').lower()
        desc = v.get('description', '')
        if 'alignment' in rule:
            suggestions.append("Adjust text alignment to meet brand vertical combination rules.")
        if 'spacing' in rule or 'space' in desc.lower():
            suggestions.append("Correct vertical spacing to required proportion (e.g., 1/2 logo height).")
        if 'typeface' in rule or 'font' in desc.lower():
            suggestions.append("Use mandated 'Kia Signature Bold' with proper weight.")
        if 'sizing' in rule or 'size' in desc.lower():
            suggestions.append("Resize elements to match specified logo width guidelines.")
        if not any(k in rule for k in ['alignment','spacing','typeface','sizing']):
            # Generic fallback per violation
            suggestions.append("Review guideline section related to this violation and adjust accordingly.")
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped[:6]  # limit to top 6 to avoid clutter


def _parse_raw_json_block(raw_text: str):
    """Attempt to parse a raw_response string that may contain fenced JSON (```json ... ```).
    Returns parsed dict or None.
    """
    if not raw_text:
        return None
    cleaned = raw_text.strip()
    # Strip markdown fences
    if cleaned.startswith('```'):
        # remove first fence line
        first_newline = cleaned.find('\n')
        if first_newline != -1:
            cleaned = cleaned[first_newline+1:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except Exception:
        return None


def _collect_recommendations(result: dict):
    """Return unified recommendation list with precedence order:
    1. Recommendations nested within violations
    2. Explicit recommendations in json_output (legacy)
    3. Recommendations from parsed raw_response JSON
    4. Derived via violations heuristic
    De-duplicate while preserving order.
    """
    json_output = result.get('json_output', {}) or {}
    violations = result.get('violations', []) or []
    final = []
    
    # First priority: recommendations nested in violations
    for violation in violations:
        if isinstance(violation, dict) and violation.get('recommendation'):
            final.append(violation['recommendation'])
    
    # Second priority: legacy recommendations array (if not generic)
    recs = json_output.get('recommendations') or []
    generic_set = {"Review the analysis for compliance details"}
    has_only_generic = len(recs) == 1 and recs[0] in generic_set
    
    if recs and not has_only_generic and not final:  # Only use if no violation recommendations
        final.extend(recs)
    
    # Third priority: Raw response recommendations
    if not final:  # Only if we haven't found any yet
        raw_text = json_output.get('raw_response')
        if raw_text:
            raw_parsed = _parse_raw_json_block(raw_text)
            raw_recs = raw_parsed.get('recommendations') if raw_parsed else None
            if raw_recs:
                final.extend(raw_recs)
    
    # Fourth priority: derive from violation heuristics
    if not final:
        derived = _derive_recommendations_from_violations(violations)
        final.extend(derived)
    
    return final


def show_detailed_results(all_results):
    """Display detailed analysis results."""
    st.markdown("---")
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
                tabs = ["📝 Summary"]
                has_raw = bool(result.get('json_output', {}).get('raw_response'))
                if has_raw:
                    tabs.append("🧪 Raw JSON")
                tab_objects = st.tabs(tabs)
                # Map for readability
                tab1 = tab_objects[0]
                tab_raw = tab_objects[1] if has_raw else None
                
                with tab1:
                    st.write("**Analysis Summary:**")
                    st.write(result['summary'])
                    
                    if result['violations']:
                        st.write("**Violations Found:**")
                        
                        # Track if any violations have recommendations
                        violations_with_recommendations = 0
                        
                        for i, violation in enumerate(result['violations']):
                            # Handle both dict and string violations
                            if isinstance(violation, dict):
                                rule = violation.get('rule_violated', 'Unknown rule')
                                description = violation.get('description', 'No description')
                                recommendation = violation.get('recommendation', '')
                                severity = violation.get('severity', '')
                                
                                # Show severity badge if available
                                severity_badge = ""
                                if severity:
                                    if severity.lower() in ['high', 'critical']:
                                        severity_badge = f" 🔴 **{severity}**"
                                    elif severity.lower() == 'medium':
                                        severity_badge = f" 🟡 **{severity}**"
                                    elif severity.lower() == 'low':
                                        severity_badge = f" 🟢 **{severity}**"
                                    else:
                                        severity_badge = f" **{severity}**"
                                
                                st.warning(f"**{rule}**{severity_badge}: {description}")
                                if recommendation:
                                    st.info(f"💡 **Recommendation**: {recommendation}")
                                    violations_with_recommendations += 1
                                else:
                                    # Try to derive recommendation from global recommendations list
                                    recs = _collect_recommendations(result)
                                    if recs and i < len(recs):
                                        st.info(f"💡 **Recommendation**: {recs[i]}")
                                        violations_with_recommendations += 1
                            elif isinstance(violation, str):
                                st.warning(violation)
                        
                        # If no violations had recommendations, show all general recommendations
                        if violations_with_recommendations == 0:
                            recs = _collect_recommendations(result)
                            if recs:
                                st.write("**Recommendations:**")
                                for rec in recs:
                                    st.info(f"💡 {rec}")
                    else:
                        st.success("✅ No violations found - asset meets brand guidelines!")
                
                if has_raw and tab_raw:
                    with tab_raw:
                        raw_text = result['json_output'].get('raw_response')
                        raw_parsed = _parse_raw_json_block(raw_text)
                        if raw_parsed:
                            st.json(raw_parsed)
                        else:
                            st.code(raw_text or "(no raw response)")


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
            
            # Convert date string to datetime if needed
            if 'date' in trend_df.columns:
                trend_df['date'] = pd.to_datetime(trend_df['date'])
            
            # Create line chart
            fig_trend = px.line(
                trend_df, 
                x='date', 
                y='compliance_rate',
                title='Compliance Rate Trend',
                markers=True
            )
            fig_trend.update_yaxis(range=[0, 100])
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info("No trend data available yet.")
    except Exception as e:
        st.error(f"Error loading trend data: {e}")

    # Recent analysis
    st.subheader("🕒 Recent Analysis")
    try:
        recent_data = get_recent_analysis(10)
        if recent_data:
            recent_df = pd.DataFrame(recent_data)
            st.dataframe(recent_df, use_container_width=True)
        else:
            st.info("No recent analysis data available.")
    except Exception as e:
        st.error(f"Error loading recent analysis: {e}")

    # Common violations
    st.subheader("⚠️ Common Violations")
    try:
        violations_data = get_common_violations(10)
        if violations_data:
            violations_df = pd.DataFrame(violations_data)
            
            # Create bar chart
            fig_violations = px.bar(
                violations_df,
                x='count',
                y='rule_violated',
                orientation='h',
                title='Most Common Violations'
            )
            fig_violations.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_violations, use_container_width=True)
        else:
            st.info("No violation data available yet.")
    except Exception as e:
        st.error(f"Error loading violations data: {e}")


def prepare_pdf_data(analysis_results):
    """
    Prepare analysis results data for PDF generation.
    
    Args:
        analysis_results: List of analysis result dictionaries
    
    Returns:
        Dictionary containing formatted data for PDF generation
    """
    if not analysis_results:
        return {}
    
    # Calculate summary statistics
    total_assets = len(analysis_results)
    compliant_count = sum(1 for r in analysis_results if r.get('compliance_status') == 'Compliant')
    non_compliant_count = sum(1 for r in analysis_results if r.get('compliance_status') == 'Non-Compliant')
    no_logo_count = sum(1 for r in analysis_results if r.get('compliance_status') == 'No Logo Found')
    error_count = sum(1 for r in analysis_results if r.get('compliance_status') == 'Error')
    
    # Calculate compliance rate
    compliance_rate = (compliant_count / total_assets * 100) if total_assets > 0 else 0
    
    # Collect all violations
    all_violations = []
    for result in analysis_results:
        violations = result.get('violations', [])
        for violation in violations:
            all_violations.append({
                'filename': result.get('filename', 'Unknown'),
                'page_number': result.get('page_number'),
                'rule_violated': violation.get('rule_violated', 'Unknown'),
                'description': violation.get('description', 'No description')
            })
    
    # Prepare formatted data
    pdf_data = {
        'summary': {
            'total_assets': total_assets,
            'compliant_count': compliant_count,
            'non_compliant_count': non_compliant_count,
            'no_logo_count': no_logo_count,
            'error_count': error_count,
            'compliance_rate': compliance_rate
        },
        'analysis_results': analysis_results,
        'violations': all_violations,
        'generated_at': datetime.now(),
        'report_title': 'Brand Compliance Analysis Report'
    }
    
    return pdf_data


if __name__ == "__main__":
    main()
