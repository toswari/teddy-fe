"""
PDF Report Generator for Brand Compliance Analysis
Generates professional, user-friendly reports for non-technical users
"""

import io
import json
import base64
from datetime import datetime
from typing import List, Dict, Any, Tuple
from fpdf import FPDF
from PIL import Image
import tempfile
import os


class BrandComplianceReportGenerator:
    """
    Professional PDF report generator for brand compliance analysis results.
    Designed to be attractive and easy to understand for non-technical users.
    """
    
    def __init__(self):
        self.pdf = None
        self.page_count = 0
        self.total_pages = 0
        
        # Color scheme - Professional brand colors
        self.colors = {
            'primary': (51, 122, 183),      # Professional blue
            'success': (92, 184, 92),       # Green for compliant
            'danger': (217, 83, 79),        # Red for non-compliant
            'warning': (240, 173, 78),      # Orange for warnings
            'light_gray': (248, 248, 248),  # Light background
            'dark_gray': (52, 58, 64),      # Dark text
            'white': (255, 255, 255),       # White background
            'border': (220, 220, 220)       # Light border
        }
        
        # Font settings for professional appearance
        self.fonts = {
            'title': ('Arial', 'B', 24),
            'subtitle': ('Arial', 'B', 16),
            'heading': ('Arial', 'B', 14),
            'body': ('Arial', '', 11),
            'small': ('Arial', '', 9),
            'footer': ('Arial', 'I', 8)
        }
    
    def create_report(self, analysis_results: List[Dict[str, Any]], 
                     session_metadata: Dict[str, Any] = None) -> bytes:
        """
        Generate a complete brand compliance PDF report.
        
        Args:
            analysis_results: List of analysis results for each asset
            session_metadata: Optional metadata about the analysis session
            
        Returns:
            PDF content as bytes
        """
        print(f"📄 Generating PDF report for {len(analysis_results)} assets...")
        
        # Initialize PDF with professional settings
        self.pdf = FPDF(orientation='P', unit='mm', format='A4')
        self.pdf.set_auto_page_break(auto=True, margin=15)
        
        # Calculate total pages (cover + 1 page per asset)
        self.total_pages = 1 + len(analysis_results)
        
        # Generate report sections
        self._create_cover_page(analysis_results, session_metadata)
        
        for i, result in enumerate(analysis_results):
            self._create_asset_analysis_page(result, i + 1)
        
        # Return PDF as bytes
        pdf_content = self.pdf.output()
        print(f"✅ PDF report generated successfully ({len(pdf_content)} bytes)")
        return pdf_content
    
    def _create_cover_page(self, analysis_results: List[Dict[str, Any]], 
                          session_metadata: Dict[str, Any]):
        """Create an attractive cover page with summary statistics."""
        self.pdf.add_page()
        self.page_count += 1
        
        # Add professional header with logo space
        self._add_header_section()
        
        # Main title with professional styling
        self.pdf.ln(20)
        self._set_font(*self.fonts['title'])
        self._set_color(*self.colors['primary'])
        self.pdf.cell(0, 15, "Brand Compliance Analysis Report", ln=True, align='C')
        
        # Subtitle with date
        self.pdf.ln(10)
        self._set_font(*self.fonts['subtitle'])
        self._set_color(*self.colors['dark_gray'])
        current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")
        self.pdf.cell(0, 10, f"Generated on {current_date}", ln=True, align='C')
        
        # Add decorative line
        self.pdf.ln(15)
        self._draw_decorative_line()
        
        # Executive Summary Box
        self.pdf.ln(20)
        self._create_summary_box(analysis_results)
        
        # Analysis Overview
        self.pdf.ln(20)
        self._create_analysis_overview(analysis_results)
        
        # Footer
        self._add_footer()
    
    def _create_summary_box(self, analysis_results: List[Dict[str, Any]]):
        """Create an attractive summary box with key statistics."""
        total_assets = len(analysis_results)
        non_compliant_count = sum(1 for result in analysis_results 
                                if result.get('json_output', {}).get('compliance_status', '').lower() == 'non-compliant')
        compliant_count = total_assets - non_compliant_count
        
        # Box background
        box_y = self.pdf.get_y()
        self._set_fill_color(*self.colors['light_gray'])
        self.pdf.rect(20, box_y, 170, 40, 'F')
        
        # Box border
        self._set_draw_color(*self.colors['border'])
        self.pdf.rect(20, box_y, 170, 40)
        
        # Content
        self.pdf.set_xy(30, box_y + 5)
        self._set_font(*self.fonts['heading'])
        self._set_color(*self.colors['primary'])
        self.pdf.cell(0, 8, "Executive Summary", ln=True)
        
        self.pdf.set_x(30)
        self._set_font(*self.fonts['body'])
        self._set_color(*self.colors['dark_gray'])
        summary_text = f"This report details the analysis of {total_assets} assets. "
        if non_compliant_count > 0:
            summary_text += f"{non_compliant_count} asset{'s' if non_compliant_count != 1 else ''} were found to be non-compliant."
        else:
            summary_text += "All assets were found to be compliant with brand guidelines."
        
        # Multi-line text handling
        self.pdf.multi_cell(150, 6, summary_text)
        
        # Statistics
        self.pdf.set_xy(30, box_y + 25)
        self._create_status_indicators(compliant_count, non_compliant_count)
        
        self.pdf.set_y(box_y + 45)
    
    def _create_status_indicators(self, compliant_count: int, non_compliant_count: int):
        """Create visual status indicators."""
        # Compliant indicator
        self._set_fill_color(*self.colors['success'])
        self.pdf.rect(self.pdf.get_x(), self.pdf.get_y(), 4, 4, 'F')
        self.pdf.set_x(self.pdf.get_x() + 8)
        self._set_font(*self.fonts['body'])
        self._set_color(*self.colors['dark_gray'])
        self.pdf.cell(40, 4, f"Compliant: {compliant_count}")
        
        # Non-compliant indicator
        self.pdf.set_x(self.pdf.get_x() + 20)
        self._set_fill_color(*self.colors['danger'])
        self.pdf.rect(self.pdf.get_x(), self.pdf.get_y(), 4, 4, 'F')
        self.pdf.set_x(self.pdf.get_x() + 8)
        self.pdf.cell(40, 4, f"Non-Compliant: {non_compliant_count}")
    
    def _create_analysis_overview(self, analysis_results: List[Dict[str, Any]]):
        """Create an overview of all analyzed assets."""
        self._set_font(*self.fonts['heading'])
        self._set_color(*self.colors['primary'])
        self.pdf.cell(0, 10, "Assets Analyzed", ln=True)
        
        self.pdf.ln(5)
        
        for i, result in enumerate(analysis_results, 1):
            filename = result.get('filename', f'Asset {i}')
            status = result.get('json_output', {}).get('compliance_status', 'Unknown')
            
            # Asset entry
            self._set_font(*self.fonts['body'])
            self._set_color(*self.colors['dark_gray'])
            self.pdf.cell(20, 8, f"{i}.")
            self.pdf.cell(120, 8, filename)
            
            # Status badge
            status_color = self.colors['success'] if status.lower() == 'compliant' else self.colors['danger']
            self._set_fill_color(*status_color)
            self._set_color(*self.colors['white'])
            self.pdf.cell(30, 8, status.upper(), align='C', fill=True, ln=True)
            
            self.pdf.ln(2)
    
    def _create_asset_analysis_page(self, result: Dict[str, Any], asset_number: int):
        """Create a detailed analysis page for a single asset."""
        self.pdf.add_page()
        self.page_count += 1
        
        filename = result.get('filename', f'Asset {asset_number}')
        json_output = result.get('json_output', {})
        compliance_status = json_output.get('compliance_status', 'Unknown')
        
        # Page header
        self._add_page_header(filename)
        
        # Image display (if available)
        self._add_asset_image(result)
        
        # Status banner
        self._add_status_banner(compliance_status)
        
        # Findings and recommendations (only for non-compliant assets)
        if compliance_status.lower() == 'non-compliant':
            self._add_findings_section(json_output)
        else:
            self._add_compliant_message(json_output)
        
        # Footer
        self._add_footer()
    
    def _add_page_header(self, filename: str):
        """Add a professional page header."""
        self._set_font(*self.fonts['subtitle'])
        self._set_color(*self.colors['primary'])
        header_text = f"Analysis for: {filename}"
        self.pdf.cell(0, 12, header_text, ln=True, align='C')
        
        # Decorative line under header
        self._draw_decorative_line()
        self.pdf.ln(10)
    
    def _add_asset_image(self, result: Dict[str, Any]):
        """Add the analyzed image to the page if available."""
        image_data = result.get('image_data')
        if not image_data:
            # Add placeholder message
            self._set_font(*self.fonts['body'])
            self._set_color(*self.colors['dark_gray'])
            self.pdf.cell(0, 10, "[Image preview not available]", ln=True, align='C')
            self.pdf.ln(5)
            return
        
        try:
            # Create temporary file for image
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
                if isinstance(image_data, str):
                    # Base64 encoded image
                    try:
                        image_bytes = base64.b64decode(image_data)
                    except Exception as e:
                        print(f"⚠️ Base64 decode error: {e}")
                        self._show_image_error()
                        return
                else:
                    # Raw bytes
                    image_bytes = image_data
                
                tmp_file.write(image_bytes)
                tmp_file.flush()
                
                # Add image label
                self._set_font(*self.fonts['body'])
                self._set_color(*self.colors['primary'])
                self.pdf.cell(0, 8, "Asset Preview:", ln=True, align='C')
                self.pdf.ln(3)
                
                # Add image to PDF (centered, max width 150mm)
                current_y = self.pdf.get_y()
                try:
                    # Get image dimensions to calculate scaling
                    with Image.open(tmp_file.name) as img:
                        # Convert to RGB if necessary
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                            
                        img_width, img_height = img.size
                        aspect_ratio = img_height / img_width
                        
                        # Scale to fit within 150mm width, 80mm height
                        max_width = 150
                        max_height = 80
                        
                        if aspect_ratio > max_height / max_width:
                            # Height is limiting factor
                            display_height = max_height
                            display_width = max_height / aspect_ratio
                        else:
                            # Width is limiting factor
                            display_width = max_width
                            display_height = max_width * aspect_ratio
                        
                        # Center the image
                        x_offset = (210 - display_width) / 2  # A4 width is 210mm
                        
                        self.pdf.image(tmp_file.name, x=x_offset, y=current_y, 
                                     w=display_width, h=display_height)
                        
                        self.pdf.set_y(current_y + display_height + 10)
                
                except Exception as e:
                    print(f"⚠️ Could not add image to PDF: {e}")
                    self._show_image_error()
                
                # Clean up temporary file
                try:
                    os.unlink(tmp_file.name)
                except:
                    pass  # Ignore cleanup errors
                
        except Exception as e:
            print(f"⚠️ Error processing image: {e}")
            self._show_image_error()
    
    def _show_image_error(self):
        """Show a user-friendly image error message."""
        self._set_font(*self.fonts['body'])
        self._set_color(*self.colors['dark_gray'])
        self.pdf.cell(0, 10, "📷 Image could not be displayed", ln=True, align='C')
        self.pdf.ln(5)
    
    def _add_status_banner(self, compliance_status: str):
        """Add a visually distinct status banner with icons."""
        banner_y = self.pdf.get_y()
        
        # Choose colors and symbols based on status
        if compliance_status.lower() == 'compliant':
            bg_color = self.colors['success']
            text = "✓ COMPLIANT"
            icon_color = self.colors['white']
        else:
            bg_color = self.colors['danger']
            text = "⚠ NON-COMPLIANT"
            icon_color = self.colors['white']
        
        # Draw banner background
        self._set_fill_color(*bg_color)
        self.pdf.rect(20, banner_y, 170, 15, 'F')
        
        # Banner text with icon
        self.pdf.set_xy(20, banner_y + 3)
        self._set_font(*self.fonts['subtitle'])
        self._set_color(*icon_color)
        self.pdf.cell(170, 9, text, align='C')
        
        self.pdf.set_y(banner_y + 20)
    
    def _add_findings_section(self, json_output: Dict[str, Any]):
        """Add detailed findings and recommendations for non-compliant assets."""
        violations = json_output.get('violations', [])
        
        if not violations:
            self._set_font(*self.fonts['body'])
            self._set_color(*self.colors['dark_gray'])
            self.pdf.cell(0, 10, "No specific violations details available.", ln=True)
            return
        
        # Section header
        self._set_font(*self.fonts['heading'])
        self._set_color(*self.colors['primary'])
        self.pdf.cell(0, 12, "Findings & Recommendations", ln=True)
        self.pdf.ln(5)
        
        for i, violation in enumerate(violations):
            if i > 0:
                # Separator line between violations
                self._draw_separator_line()
                self.pdf.ln(5)
            
            self._add_violation_details(violation, i + 1)
    
    def _add_violation_details(self, violation: Dict[str, Any], violation_number: int):
        """Add details for a single violation."""
        rule_violated = violation.get('rule_violated', f'Violation {violation_number}')
        description = violation.get('description', 'No description available')
        
        # Clean the description for business users
        clean_description = self._clean_text_for_business_users(description)
        if not clean_description:
            clean_description = "This element does not meet brand guidelines and needs to be corrected."
        
        # Violation header with warning icon
        self._set_font(*self.fonts['heading'])
        self._set_color(*self.colors['danger'])
        violation_text = f"⚠ Violation {violation_number}: {rule_violated}"
        self.pdf.cell(0, 8, violation_text, ln=True)
        
        # Issue description
        self.pdf.ln(2)
        self._set_font(*self.fonts['body'])
        self._set_color(*self.colors['dark_gray'])
        self.pdf.cell(20, 6, "🔍 Issue:")
        self._set_font('Arial', 'B', 11)
        remaining_width = 170
        self.pdf.multi_cell(remaining_width, 6, clean_description)
        
        # Recommendation
        self.pdf.ln(3)
        recommendation = self._generate_user_friendly_recommendation(clean_description, rule_violated)
        self._set_font(*self.fonts['body'])
        self._set_color(*self.colors['dark_gray'])
        self.pdf.cell(20, 6, "🔧 Fix:")
        self._set_font('Arial', '', 11)
        self._set_color(*self.colors['primary'])
        self.pdf.multi_cell(remaining_width, 6, recommendation)
        
        self.pdf.ln(5)
    
    def _add_compliant_message(self, json_output: Dict[str, Any]):
        """Add a positive message for compliant assets with checkmark icon."""
        self._set_font(*self.fonts['heading'])
        self._set_color(*self.colors['success'])
        self.pdf.cell(0, 12, "✓ Excellent! This asset meets all brand guidelines.", ln=True)
        
        self.pdf.ln(5)
        
        # Add summary if available (clean it up for business users)
        summary = json_output.get('summary', '')
        if summary:
            # Clean up any JSON formatting from summary
            clean_summary = self._clean_text_for_business_users(summary)
            if clean_summary and clean_summary != "Analysis completed":
                self._set_font(*self.fonts['body'])
                self._set_color(*self.colors['dark_gray'])
                self.pdf.multi_cell(0, 6, clean_summary)
        
        # Add any recommendations for compliant assets
        recommendations = json_output.get('recommendations', [])
        if recommendations:
            self.pdf.ln(5)
            self._set_font(*self.fonts['body'])
            self._set_color(*self.colors['dark_gray'])
            self.pdf.cell(0, 8, "💡 Additional suggestions:", ln=True)
            
            for rec in recommendations:
                clean_rec = self._clean_text_for_business_users(rec)
                if clean_rec:
                    self.pdf.cell(10, 6, "•")
                    self.pdf.multi_cell(160, 6, clean_rec)
                    self.pdf.ln(2)
    
    def _generate_user_friendly_recommendation(self, description: str, rule_violated: str) -> str:
        """Convert technical descriptions into user-friendly recommendations."""
        # Rule-based mapping for common issues
        recommendations = {
            'alignment': 'Align the text to the left so its left edge lines up perfectly with the left edge of the Kia logo above it.',
            'color': 'Update the colors to match the official Kia brand colors specified in the brand guidelines.',
            'font': 'Change the font to the official Kia brand font as specified in the brand guidelines.',
            'spacing': 'Adjust the spacing between elements according to the brand guidelines measurements.',
            'logo': 'Ensure the Kia logo is used correctly without modifications and in the proper size ratio.',
            'proportion': 'Resize elements to match the correct proportions specified in the brand guidelines.',
            'position': 'Reposition the elements to match the correct layout specified in the brand guidelines.'
        }
        
        description_lower = description.lower()
        
        # Check for specific rule types
        for rule_type, recommendation in recommendations.items():
            if rule_type in description_lower or rule_type in rule_violated.lower():
                return recommendation
        
        # Generic recommendation if no specific rule is matched
        return "Please review this element against the brand guidelines and make the necessary adjustments to ensure compliance."
    
    def _add_header_section(self):
        """Add a professional header section with branding space."""
        # Logo placeholder area
        self._set_fill_color(*self.colors['light_gray'])
        self.pdf.rect(20, 20, 50, 20, 'F')
        
        self.pdf.set_xy(25, 25)
        self._set_font(*self.fonts['small'])
        self._set_color(*self.colors['dark_gray'])
        self.pdf.cell(40, 10, "Brand Compliance", align='C')
        self.pdf.set_xy(25, 30)
        self.pdf.cell(40, 10, "AI Specialist", align='C')
    
    def _add_footer(self):
        """Add a professional footer to the page."""
        # Position footer at bottom of page
        self.pdf.set_y(-15)
        
        # Footer line
        self._set_draw_color(*self.colors['border'])
        self.pdf.line(20, self.pdf.get_y(), 190, self.pdf.get_y())
        
        # Footer text
        self.pdf.set_y(-12)
        self._set_font(*self.fonts['footer'])
        self._set_color(*self.colors['dark_gray'])
        footer_text = f"Report generated by AI Brand Compliance Specialist | Page {self.page_count} of {self.total_pages}"
        self.pdf.cell(0, 10, footer_text, align='C')
    
    def _draw_decorative_line(self):
        """Draw a decorative line across the page."""
        current_y = self.pdf.get_y()
        self._set_draw_color(*self.colors['primary'])
        self.pdf.set_line_width(0.5)
        self.pdf.line(30, current_y, 180, current_y)
        self.pdf.set_line_width(0.2)  # Reset line width
    
    def _draw_separator_line(self):
        """Draw a separator line between sections."""
        current_y = self.pdf.get_y()
        self._set_draw_color(*self.colors['border'])
        self.pdf.line(20, current_y, 190, current_y)
    
    # Utility methods for consistent styling
    def _set_font(self, family: str, style: str = '', size: int = 11):
        """Set font with error handling."""
        try:
            self.pdf.set_font(family, style, size)
        except Exception:
            # Fallback to default font
            self.pdf.set_font('Arial', style, size)
    
    def _set_color(self, r: int, g: int, b: int):
        """Set text color."""
        self.pdf.set_text_color(r, g, b)
    
    def _set_fill_color(self, r: int, g: int, b: int):
        """Set fill color."""
        self.pdf.set_fill_color(r, g, b)
    
    def _set_draw_color(self, r: int, g: int, b: int):
        """Set draw color."""
        self.pdf.set_draw_color(r, g, b)
    
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


def generate_compliance_report(analysis_results: List[Dict[str, Any]], 
                             session_metadata: Dict[str, Any] = None) -> bytes:
    """
    Main function to generate a brand compliance PDF report.
    
    Args:
        analysis_results: List of analysis results from the compliance checker
        session_metadata: Optional metadata about the analysis session
        
    Returns:
        PDF content as bytes
    """
    generator = BrandComplianceReportGenerator()
    return generator.create_report(analysis_results, session_metadata)


# Utility function to parse LLM response for violations
def parse_llm_response(json_output: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Parse the detailed_findings array from LLM JSON response.
    
    Args:
        json_output: The JSON response from the LLM
        
    Returns:
        List of violations with rule_violated and description
    """
    violations = []
    
    # Check for violations in the response
    if 'violations' in json_output:
        for violation in json_output['violations']:
            if isinstance(violation, dict):
                violations.append({
                    'rule_violated': violation.get('rule_violated', 'Unknown Rule'),
                    'description': violation.get('description', 'No description available')
                })
            elif isinstance(violation, str):
                # Handle string violations
                violations.append({
                    'rule_violated': 'Brand Guideline Violation',
                    'description': violation
                })
    
    # Check for detailed_findings if violations not found
    elif 'detailed_findings' in json_output:
        for finding in json_output['detailed_findings']:
            if isinstance(finding, dict):
                violations.append({
                    'rule_violated': finding.get('rule_violated', finding.get('rule', 'Unknown Rule')),
                    'description': finding.get('description', finding.get('issue', 'No description available'))
                })
    
    return violations
