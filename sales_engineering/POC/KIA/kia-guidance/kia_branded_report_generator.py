"""
Kia-Branded WeasyPrint PDF Report Generator
Matches official Kia website design theme and branding
"""

import io
import json
import base64
from datetime import datetime
from typing import List, Dict, Any
from weasyprint import HTML, CSS
from PIL import Image
import tempfile
import os


class KiaBrandedReportGenerator:
    """
    Professional PDF report generator using official Kia design theme.
    Matches kia.com website styling and branding.
    """
    
    def __init__(self):
        self.page_count = 0
        
        # Official Kia-inspired CSS styles
        self.css_styles = """
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&display=swap');
        
        @page {
            size: A4;
            margin: 15mm;
            @bottom-center {
                content: "Powered by AI Brand Compliance Specialist | Page " counter(page);
                font-family: 'Poppins', Arial, sans-serif;
                font-size: 8pt;
                color: #666;
                border-top: 1px solid #e5e5e5;
                padding-top: 8px;
            }
        }
        
        body {
            font-family: 'Poppins', Arial, sans-serif;
            line-height: 1.6;
            color: #2c2c2c;
            margin: 0;
            padding: 0;
            background: #ffffff;
        }
        
        /* Kia-inspired header */
        .kia-header {
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 50%, #000000 100%);
            color: white;
            padding: 40px 30px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 40px;
            position: relative;
            overflow: hidden;
        }
        
        .kia-header::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #ff0000 0%, #cc0000 50%, #ff0000 100%);
        }
        
        .main-title {
            font-size: 32pt;
            font-weight: 700;
            margin-bottom: 12px;
            letter-spacing: -0.5px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .subtitle {
            font-size: 16pt;
            font-weight: 300;
            opacity: 0.9;
            margin-bottom: 0;
            letter-spacing: 0.5px;
        }
        
        /* Modern summary box */
        .summary-box {
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border: 1px solid #e9ecef;
            border-radius: 16px;
            padding: 35px;
            margin: 40px 0;
            box-shadow: 0 8px 25px rgba(0,0,0,0.08);
            position: relative;
        }
        
        .summary-box::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #ff0000 0%, #cc0000 100%);
            border-radius: 16px 16px 0 0;
        }
        
        .summary-title {
            font-size: 24pt;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .summary-text {
            font-size: 14pt;
            margin-bottom: 25px;
            text-align: center;
            color: #4a4a4a;
            line-height: 1.7;
        }
        
        .status-indicators {
            display: flex;
            justify-content: space-around;
            margin-top: 25px;
        }
        
        .status-item {
            text-align: center;
            padding: 20px;
            border-radius: 12px;
            flex: 1;
            margin: 0 10px;
        }
        
        .status-item.compliant {
            background: linear-gradient(135deg, #e8f5e8 0%, #f0fff0 100%);
            border: 2px solid #28a745;
            color: #155724;
        }
        
        .status-item.non-compliant {
            background: linear-gradient(135deg, #fff5f5 0%, #ffe6e6 100%);
            border: 2px solid #dc3545;
            color: #721c24;
        }
        
        .status-icon {
            font-size: 20pt;
            margin-bottom: 8px;
            display: block;
        }
        
        .status-number {
            font-size: 28pt;
            font-weight: 700;
            display: block;
            margin-bottom: 5px;
        }
        
        .status-label {
            font-size: 12pt;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Asset overview */
        .asset-overview {
            margin: 40px 0;
        }
        
        .section-title {
            font-size: 22pt;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 25px;
            padding-bottom: 12px;
            border-bottom: 3px solid #ff0000;
            position: relative;
        }
        
        .asset-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 18px 20px;
            margin-bottom: 12px;
            border-radius: 10px;
            background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
            border: 1px solid #e9ecef;
            transition: all 0.3s ease;
        }
        
        .asset-item:hover {
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        
        .asset-name {
            font-weight: 500;
            flex-grow: 1;
            color: #2c2c2c;
            font-size: 12pt;
        }
        
        .status-badge {
            padding: 8px 16px;
            border-radius: 25px;
            color: white;
            font-weight: 600;
            font-size: 10pt;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .status-badge.compliant {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        }
        
        .status-badge.non-compliant {
            background: linear-gradient(135deg, #dc3545 0%, #e74c3c 100%);
        }
        
        /* Page breaks and individual pages */
        .page-break {
            page-break-before: always;
        }
        
        .asset-header {
            background: linear-gradient(135deg, #1a1a1a 0%, #2c2c2c 100%);
            color: white;
            padding: 30px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
            position: relative;
        }
        
        .asset-header::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #ff0000 0%, #cc0000 100%);
            border-radius: 12px 12px 0 0;
        }
        
        .asset-title {
            font-size: 20pt;
            font-weight: 600;
            margin: 0;
        }
        
        /* Image containers */
        .image-container {
            text-align: center;
            margin: 30px 0;
            padding: 25px;
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            border-radius: 12px;
            border: 1px solid #e9ecef;
        }
        
        .image-label {
            font-size: 16pt;
            font-weight: 600;
            color: #1a1a1a;
            margin-bottom: 20px;
        }
        
        .asset-image {
            max-width: 100%;
            max-height: 350px;
            border-radius: 10px;
            box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        }
        
        .image-placeholder {
            color: #6c757d;
            font-style: italic;
            padding: 50px;
            background: linear-gradient(135deg, #e9ecef 0%, #f8f9fa 100%);
            border-radius: 10px;
            font-size: 14pt;
        }
        
        /* Status banners */
        .status-banner {
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            font-size: 18pt;
            font-weight: 700;
            margin: 30px 0;
            color: white;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .status-banner.compliant {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            box-shadow: 0 4px 15px rgba(40, 167, 69, 0.3);
        }
        
        .status-banner.non-compliant {
            background: linear-gradient(135deg, #dc3545 0%, #e74c3c 100%);
            box-shadow: 0 4px 15px rgba(220, 53, 69, 0.3);
        }
        
        /* Findings and violations */
        .findings-section {
            margin: 40px 0;
        }
        
        .violation-item {
            background: linear-gradient(135deg, #fff8f8 0%, #ffffff 100%);
            border-left: 5px solid #dc3545;
            padding: 25px;
            margin-bottom: 25px;
            border-radius: 0 12px 12px 0;
            box-shadow: 0 4px 12px rgba(220, 53, 69, 0.1);
        }
        
        .violation-header {
            font-size: 16pt;
            font-weight: 600;
            color: #dc3545;
            margin-bottom: 20px;
        }
        
        .issue-section, .fix-section {
            margin: 20px 0;
        }
        
        .issue-label, .fix-label {
            font-weight: 600;
            color: #2c2c2c;
            margin-bottom: 12px;
            font-size: 12pt;
            display: flex;
            align-items: center;
        }
        
        .label-icon {
            margin-right: 8px;
            font-size: 14pt;
        }
        
        .issue-text {
            background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #6c757d;
            line-height: 1.7;
        }
        
        .fix-text {
            background: linear-gradient(135deg, #e8f4fd 0%, #f0f9ff 100%);
            padding: 15px;
            border-radius: 8px;
            border-left: 3px solid #007bff;
            color: #004085;
            line-height: 1.7;
        }
        
        /* Compliant messages */
        .compliant-message {
            background: linear-gradient(135deg, #f0fff4 0%, #e8f5e8 100%);
            border: 2px solid #28a745;
            border-radius: 16px;
            padding: 30px;
            text-align: center;
            margin: 30px 0;
            box-shadow: 0 6px 20px rgba(40, 167, 69, 0.15);
        }
        
        .compliant-title {
            font-size: 18pt;
            font-weight: 600;
            color: #155724;
            margin-bottom: 20px;
        }
        
        .recommendations {
            margin: 25px 0;
            text-align: left;
        }
        
        .recommendation-item {
            display: flex;
            margin: 12px 0;
            padding: 10px;
            align-items: flex-start;
        }
        
        .recommendation-bullet {
            margin-right: 12px;
            color: #007bff;
            font-weight: 700;
            font-size: 12pt;
        }
        
        .recommendation-text {
            flex: 1;
            line-height: 1.6;
        }
        
        /* Kia branding elements */
        .kia-badge {
            display: inline-block;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 10pt;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin: 10px 0;
        }
        
        .quality-badge {
            background: linear-gradient(135deg, #ff0000 0%, #cc0000 100%);
            color: white;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 9pt;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            display: inline-block;
            margin-left: 10px;
        }
        """
    
    def create_report(self, analysis_results: List[Dict[str, Any]], 
                     session_metadata: Dict[str, Any] = None) -> bytes:
        """Create a comprehensive PDF report using Kia official design theme."""
        
        # Generate HTML content
        html_content = self._generate_html(analysis_results, session_metadata)
        
        # Create PDF using WeasyPrint
        html_doc = HTML(string=html_content)
        css_doc = CSS(string=self.css_styles)
        
        pdf_bytes = html_doc.write_pdf(stylesheets=[css_doc])
        
        print(f"✅ Kia-branded PDF report generated successfully ({len(pdf_bytes)} bytes)")
        return pdf_bytes
    
    def _generate_html(self, analysis_results: List[Dict[str, Any]], 
                      session_metadata: Dict[str, Any]) -> str:
        """Generate the complete HTML content with Kia branding."""
        
        # Calculate statistics
        total_assets = len(analysis_results)
        non_compliant_count = sum(1 for result in analysis_results 
                                if result.get('json_output', {}).get('compliance_status', '').lower() == 'non-compliant')
        compliant_count = total_assets - non_compliant_count
        
        current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Kia Brand Compliance Analysis Report</title>
        </head>
        <body>
            <!-- Kia-styled Cover Page -->
            <div class="kia-header">
                <h1 class="main-title">🎯 Kia Brand Compliance Analysis</h1>
                <p class="subtitle">📅 {current_date}</p>
                <div class="kia-badge">Official Brand Guidelines Compliance</div>
            </div>
            
            <div class="summary-box">
                <h2 class="summary-title">📊 Executive Summary</h2>
                <p class="summary-text">
                    This comprehensive analysis examines {total_assets} brand asset{"s" if total_assets != 1 else ""} 
                    against official Kia design guidelines and standards.
                    {f"Found {non_compliant_count} asset{'s' if non_compliant_count != 1 else ''} requiring attention to maintain brand consistency." if non_compliant_count > 0 else "All assets demonstrate excellent adherence to Kia brand standards."}
                </p>
                
                <div class="status-indicators">
                    <div class="status-item compliant">
                        <span class="status-icon">✅</span>
                        <span class="status-number">{compliant_count}</span>
                        <span class="status-label">Compliant</span>
                    </div>
                    <div class="status-item non-compliant">
                        <span class="status-icon">⚠️</span>
                        <span class="status-number">{non_compliant_count}</span>
                        <span class="status-label">Needs Review</span>
                    </div>
                </div>
            </div>
            
            <div class="asset-overview">
                <h2 class="section-title">📋 Brand Assets Analyzed<span class="quality-badge">Quality Assured</span></h2>
                {self._generate_asset_overview_html(analysis_results)}
            </div>
            
            <!-- Individual Asset Analysis Pages -->
            {self._generate_asset_pages_html(analysis_results)}
        </body>
        </html>
        """
        
        return html
    
    def _generate_asset_overview_html(self, analysis_results: List[Dict[str, Any]]) -> str:
        """Generate HTML for the asset overview section with Kia styling."""
        html = ""
        
        for i, result in enumerate(analysis_results, 1):
            filename = result.get('filename', f'Asset {i}')
            status = result.get('json_output', {}).get('compliance_status', 'Unknown')
            
            status_class = 'compliant' if status.lower() == 'compliant' else 'non-compliant'
            status_icon = '✅' if status.lower() == 'compliant' else '⚠️'
            
            html += f"""
            <div class="asset-item">
                <span class="asset-name">{i}. {filename}</span>
                <span class="status-badge {status_class}">
                    {status_icon} {status.upper()}
                </span>
            </div>
            """
        
        return html
    
    def _generate_asset_pages_html(self, analysis_results: List[Dict[str, Any]]) -> str:
        """Generate HTML for individual asset analysis pages with Kia branding."""
        html = ""
        
        for i, result in enumerate(analysis_results, 1):
            filename = result.get('filename', f'Asset {i}')
            json_output = result.get('json_output', {})
            compliance_status = json_output.get('compliance_status', 'Unknown')
            
            html += f"""
            <div class="page-break">
                <div class="asset-header">
                    <h1 class="asset-title">🔍 Brand Analysis: {filename}</h1>
                    <div class="kia-badge">Kia Design Standards Review</div>
                </div>
                
                {self._generate_image_html(result)}
                {self._generate_status_banner_html(compliance_status)}
                
                {self._generate_findings_html(json_output) if compliance_status.lower() == 'non-compliant' else self._generate_compliant_message_html(json_output)}
            </div>
            """
        
        return html
    
    def _generate_image_html(self, result: Dict[str, Any]) -> str:
        """Generate HTML for asset image display with Kia styling."""
        image_data = result.get('image_data')
        
        if not image_data:
            return """
            <div class="image-container">
                <div class="image-label">📷 Asset Preview</div>
                <div class="image-placeholder">
                    📷 Brand asset image not available for analysis
                </div>
            </div>
            """
        
        try:
            # Create temporary file for image
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                if isinstance(image_data, str):
                    # Base64 encoded image
                    try:
                        image_bytes = base64.b64decode(image_data)
                    except Exception as e:
                        print(f"⚠️ Base64 decode error: {e}")
                        return self._generate_image_error_html()
                else:
                    # Raw bytes
                    image_bytes = image_data
                
                tmp_file.write(image_bytes)
                tmp_file.flush()
                
                # Convert to base64 for HTML embedding
                with open(tmp_file.name, 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                # Clean up temporary file
                try:
                    os.unlink(tmp_file.name)
                except:
                    pass
                
                return f"""
                <div class="image-container">
                    <div class="image-label">📷 Brand Asset Preview</div>
                    <img src="data:image/jpeg;base64,{img_base64}" 
                         alt="Kia Brand Asset" class="asset-image">
                </div>
                """
                
        except Exception as e:
            print(f"⚠️ Error processing image: {e}")
            return self._generate_image_error_html()
    
    def _generate_image_error_html(self) -> str:
        """Generate HTML for image error display."""
        return """
        <div class="image-container">
            <div class="image-label">📷 Asset Preview</div>
            <div class="image-placeholder">
                📷 Brand asset image could not be displayed
            </div>
        </div>
        """
    
    def _generate_status_banner_html(self, compliance_status: str) -> str:
        """Generate HTML for status banner with Kia styling."""
        if compliance_status.lower() == 'compliant':
            return """
            <div class="status-banner compliant">
                ✅ Brand Guidelines Compliant
            </div>
            """
        else:
            return """
            <div class="status-banner non-compliant">
                ⚠️ Brand Guidelines Review Required
            </div>
            """
    
    def _generate_findings_html(self, json_output: Dict[str, Any]) -> str:
        """Generate HTML for findings and recommendations with Kia styling."""
        violations = json_output.get('violations', [])
        
        if not violations:
            return """
            <div class="findings-section">
                <h2 class="section-title">🔍 Brand Compliance Review</h2>
                <p>No specific brand guideline violations detected in this analysis.</p>
            </div>
            """
        
        html = """
        <div class="findings-section">
            <h2 class="section-title">🔍 Brand Compliance Issues</h2>
        """
        
        for i, violation in enumerate(violations, 1):
            rule_violated = violation.get('rule_violated', f'Brand Standard {i}')
            description = violation.get('description', 'No description available')
            
            # Clean the description for business users
            clean_description = self._clean_text_for_business_users(description)
            if not clean_description:
                clean_description = "This element does not align with Kia brand guidelines and requires adjustment."
            
            # Generate recommendation
            recommendation = self._generate_user_friendly_recommendation(clean_description, rule_violated)
            
            html += f"""
            <div class="violation-item">
                <div class="violation-header">
                    ⚠️ Brand Standard Violation {i}: {rule_violated}
                </div>
                
                <div class="issue-section">
                    <div class="issue-label">
                        <span class="label-icon">🔍</span>
                        Issue Identified:
                    </div>
                    <div class="issue-text">{clean_description}</div>
                </div>
                
                <div class="fix-section">
                    <div class="fix-label">
                        <span class="label-icon">🔧</span>
                        Recommended Action:
                    </div>
                    <div class="fix-text">{recommendation}</div>
                </div>
            </div>
            """
        
        html += "</div>"
        return html
    
    def _generate_compliant_message_html(self, json_output: Dict[str, Any]) -> str:
        """Generate HTML for compliant asset message with Kia styling."""
        html = """
        <div class="compliant-message">
            <div class="compliant-title">✅ Outstanding Brand Compliance!</div>
            <p>This asset demonstrates excellent adherence to Kia design standards and brand guidelines.</p>
        """
        
        # Add summary if available
        summary = json_output.get('summary', '')
        if summary:
            clean_summary = self._clean_text_for_business_users(summary)
            if clean_summary and clean_summary != "Analysis completed":
                html += f"<p><strong>Analysis Summary:</strong> {clean_summary}</p>"
        
        # Add recommendations
        recommendations = json_output.get('recommendations', [])
        if recommendations:
            html += """
            <div class="recommendations">
                <div class="fix-label">
                    <span class="label-icon">💡</span>
                    Enhancement Suggestions:
                </div>
            """
            for rec in recommendations:
                clean_rec = self._clean_text_for_business_users(rec)
                if clean_rec:
                    html += f"""
                    <div class="recommendation-item">
                        <span class="recommendation-bullet">•</span>
                        <span class="recommendation-text">{clean_rec}</span>
                    </div>
                    """
            html += "</div>"
        
        html += "</div>"
        return html
    
    def _clean_text_for_business_users(self, text: str) -> str:
        """Clean text to remove JSON formatting and make it business-friendly."""
        if not text:
            return ""
        
        # Remove JSON formatting characters
        cleaned = text.replace('```json', '').replace('```', '').replace('\\n', ' ')
        
        # Remove JSON structural elements
        import re
        cleaned = re.sub(r'[{}"\[\]]', '', cleaned)
        
        # Remove JSON field names
        cleaned = re.sub(r'(compliance_status|logo_type|summary|violations|recommendations|confidence_score):\s*', '', cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # If it still looks like JSON or is empty, return empty string
        if not cleaned or len(cleaned) < 10 or cleaned.startswith('{') or cleaned.endswith('}'):
            return ""
        
        # Ensure it ends with proper punctuation
        if cleaned and not cleaned.endswith(('.', '!', '?')):
            cleaned += '.'
        
        return cleaned
    
    def _generate_user_friendly_recommendation(self, description: str, rule_violated: str) -> str:
        """Convert technical descriptions into user-friendly recommendations."""
        # Kia-specific rule-based mapping
        recommendations = {
            'alignment': 'Align elements according to Kia\'s grid system to ensure consistent visual hierarchy and professional presentation.',
            'color': 'Update colors to match the official Kia brand color palette as specified in the current brand guidelines.',
            'font': 'Replace with approved Kia typography families to maintain brand consistency and readability standards.',
            'spacing': 'Adjust spacing and margins to follow Kia\'s design specifications for optimal visual balance.',
            'logo': 'Ensure the Kia logo follows official usage guidelines including size, placement, and clearspace requirements.',
            'proportion': 'Resize elements to match Kia\'s approved proportional relationships and sizing standards.',
            'position': 'Reposition elements to align with Kia\'s layout guidelines and visual hierarchy principles.'
        }
        
        description_lower = description.lower()
        
        # Check for specific rule types
        for rule_type, recommendation in recommendations.items():
            if rule_type in description_lower or rule_type in rule_violated.lower():
                return recommendation
        
        # Generic recommendation if no specific rule is matched
        return "Please review this element against the current Kia brand guidelines and make necessary adjustments to ensure full compliance with Kia design standards."


def generate_kia_compliance_report(analysis_results: List[Dict[str, Any]], 
                                 session_metadata: Dict[str, Any] = None) -> bytes:
    """
    Generate a Kia-branded compliance PDF report.
    
    Args:
        analysis_results: List of analysis results from the AI model
        session_metadata: Optional metadata about the analysis session
    
    Returns:
        bytes: PDF content as bytes with official Kia branding
    """
    generator = KiaBrandedReportGenerator()
    return generator.create_report(analysis_results, session_metadata)
