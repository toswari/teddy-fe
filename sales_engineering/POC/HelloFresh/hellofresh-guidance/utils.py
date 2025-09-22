import fitz  # PyMuPDF
from fpdf import FPDF

def extract_images_from_pdf(pdf_bytes):
    """Extracts images from a PDF file."""
    images = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        images.append(pix.tobytes("png"))
    doc.close()  # Close the document
    return images

def generate_report(results):
    """Generates a consolidated PDF report from analysis results."""
    pdf = FPDF()
    pdf.set_margins(20, 20, 20)  # Set margins: left, top, right
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "HelloFresh Brand Compliance Analysis Report", ln=True, align="C")
    pdf.ln(10)  # Add some space
    
    # Add summary
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 10, "Executive Summary", ln=True)
    pdf.ln(5)
    
    total_assets = len(results)
    compliant_count = sum(1 for r in results if r.get('compliance_status') == 'Compliant')
    non_compliant_count = sum(1 for r in results if r.get('compliance_status') == 'Non-Compliant')
    no_logo_count = sum(1 for r in results if r.get('compliance_status') == 'No Logo Found')
    
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 8, f"Total Assets Analyzed: {total_assets}", ln=True)
    pdf.cell(0, 8, f"Compliant: {compliant_count}", ln=True)
    pdf.cell(0, 8, f"Non-Compliant: {non_compliant_count}", ln=True)
    pdf.cell(0, 8, f"No Logo Found: {no_logo_count}", ln=True)
    pdf.ln(10)
    
    # Detailed results
    for i, result in enumerate(results, 1):
        if pdf.get_y() > 250:  # Check if near bottom of page
            pdf.add_page()
        
        pdf.set_font("Arial", "B", 12)
        
        # Asset name with page number if applicable
        asset_name = result.get('filename', f'Asset {i}')
        if result.get('page_number'):
            asset_name += f" (Page {result['page_number']})"
        
        pdf.cell(0, 10, f"Asset {i}: {asset_name}", ln=True)
        pdf.ln(2)
        
        pdf.set_font("Arial", "", 11)
        
        # Status
        status = result.get('compliance_status', result.get('status', 'Unknown'))
        pdf.cell(0, 8, f"Status: {status}", ln=True)
        
        # Summary
        summary_text = result.get('summary', 'No summary available')
        pdf.cell(0, 8, "Summary:", ln=True)
        
        # Break down the summary into smaller chunks if needed
        if len(summary_text) > 80:  # If text is too long, split it
            words = summary_text.split(' ')
            lines = []
            current_line = ''
            for word in words:
                if len(current_line + word) < 80:
                    current_line += word + ' '
                else:
                    lines.append(current_line.strip())
                    current_line = word + ' '
            if current_line:
                lines.append(current_line.strip())
            for line in lines:
                pdf.cell(0, 6, f"  {line}", ln=True)
        else:
            pdf.cell(0, 8, f"  {summary_text}", ln=True)
        
        # Violations
        violations = result.get('violations', [])
        if violations:
            pdf.ln(2)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 8, "Violations Found:", ln=True)
            pdf.set_font("Arial", "", 10)
            for violation in violations:
                rule = violation.get('rule_violated', 'Unknown Rule')
                desc = violation.get('description', 'No description')
                pdf.cell(0, 6, f"  - {rule}: {desc[:60]}{'...' if len(desc) > 60 else ''}", ln=True)
        
        pdf.ln(8)  # Space between assets
        
    return bytes(pdf.output(dest='S'))
