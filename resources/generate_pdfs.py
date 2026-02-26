"""
Generate sample PDF files for testing from text fixtures
Run this once to create PDFs: python resources/generate_pdfs.py
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch
import os

def generate_pdf(text_content, output_path):
    """Generate PDF from text content"""
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom style for body text
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=11,
        leading=14,
        spaceAfter=6,
    )
    
    # Split text into lines and add to story
    for line in text_content.split('\n'):
        if line.strip():
            story.append(Paragraph(line, body_style))
        else:
            story.append(Spacer(1, 0.1*inch))
    
    doc.build(story)
    print(f"✓ Created: {output_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    
    # Dividend notice
    dividend_text = """BHP Group Limited
ABN 12 345 678 901
ASX Code: BHP
ISIN: AU0000014844

Notice of Dividend

The Board of BHP Group Limited hereby gives notice that a fully paid ordinary dividend of $0.45 per share has been declared.

Announcement Date: 15 February 2026
Ex-Date: 15 March 2026
Record Date: 17 March 2026
Payment Date: 1 April 2026

Franking Information:
The dividend is 100% franked.
Franking tax credit: $0.1929 per share

Currency: AUD

For further information, please contact our Investor Relations team."""
    
    generate_pdf(dividend_text, os.path.join(base_dir, 'sample-dividend-notice.pdf'))
    
    # Stock split
    split_text = """Rio Tinto PLC
ASX Code: RIO
ISIN: AU96004458985

Stock Split Announcement

Rio Tinto announces a share subdivision (split) on the following basis:

Subdivision Ratio: 1 share for every 2 held

Ex-Date: 1 May 2026
Record Date: 5 May 2026
Implementation Date: 15 May 2026

The new shares will be issued and trading will commence on 15 May 2026.
All existing shareholders will receive the additional shares automatically.

Currency: AUD"""
    
    generate_pdf(split_text, os.path.join(base_dir, 'sample-stock-split.pdf'))
    
    print("\nSample PDFs generated successfully!")
    print(f"Location: {base_dir}")
    print("\nTest with curl:")
    print('  curl -X POST -F "file=@resources/sample-dividend-notice.pdf" http://localhost:8000/extract')
    print('  curl -X POST -F "file=@resources/sample-stock-split.pdf" http://localhost:8000/extract')
