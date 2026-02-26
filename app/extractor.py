"""
PDF extraction module: text, tables, and OCR fallback
Handles digital PDFs and scanned images
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    import camelot
except ImportError:
    camelot = None

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

logger = logging.getLogger(__name__)


class PDFExtractor:
    """Extract text, tables, and apply OCR from PDF files"""
    
    def __init__(self):
        self.tesseract_available = self._check_tesseract()
    
    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available"""
        if pytesseract is None:
            logger.warning("pytesseract not installed, OCR disabled")
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception as e:
            logger.warning(f"Tesseract not available: {e}")
            return False
    
    def extract_from_pdf(self, pdf_path: str) -> Dict:
        """
        Extract text, tables, and metadata from PDF
        
        Returns:
            {
                "doc_id": str,
                "pages": [
                    {
                        "page_num": int,
                        "text": str,
                        "tables": List[str],
                        "ocr_used": bool
                    }
                ],
                "extraction_timestamp": str,
                "ocr_used_pages": List[int]
            }
        """
        if not fitz:
            raise ImportError("PyMuPDF (fitz) not installed")
        
        result = {
            "pages": [],
            "ocr_used_pages": [],
            "extraction_timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            logger.error(f"Failed to open PDF {pdf_path}: {e}")
            raise
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_data = {
                "page_num": page_num + 1,
                "text": "",
                "tables": [],
                "ocr_used": False
            }
            
            # Try text extraction first
            text = page.get_text()
            page_data["text"] = text
            
            # If text is too sparse, try OCR
            if len(text.strip()) < 50 and self.tesseract_available:
                logger.info(f"Page {page_num + 1}: Sparse text (<50 chars), trying OCR")
                ocr_text = self._ocr_page(page, page_num)
                if ocr_text:
                    page_data["text"] = ocr_text
                    page_data["ocr_used"] = True
                    result["ocr_used_pages"].append(page_num + 1)
            
            # Try table extraction with camelot (requires external file)
            if camelot:
                try:
                    tables = self._extract_tables_from_page(pdf_path, page_num + 1)
                    page_data["tables"] = tables
                except Exception as e:
                    logger.debug(f"Table extraction failed for page {page_num + 1}: {e}")
            
            result["pages"].append(page_data)
        
        doc.close()
        return result
    
    def _ocr_page(self, page: "fitz.Page", page_num: int) -> str:
        """Apply OCR to PDF page using Tesseract"""
        if not pytesseract or not Image:
            return ""
        
        try:
            # Render page to image
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
            img_data = pix.tobytes("png")
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], img_data)
            
            # Run OCR
            text = pytesseract.image_to_string(img)
            logger.info(f"OCR extracted {len(text)} chars from page {page_num}")
            return text
        except Exception as e:
            logger.error(f"OCR failed for page {page_num}: {e}")
            return ""
    
    def _extract_tables_from_page(self, pdf_path: str, page_num: int) -> List[str]:
        """Extract tables from specific page using Camelot"""
        try:
            # Try lattice method first (for bordered tables)
            tables_lattice = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor="lattice"
            )
            
            # Also try stream method (for borderless tables)
            tables_stream = camelot.read_pdf(
                pdf_path,
                pages=str(page_num),
                flavor="stream"
            )
            
            all_tables = list(tables_lattice) + list(tables_stream)
            
            # Convert to CSV strings for storage
            result = []
            for table in all_tables:
                csv_str = table.to_csv()
                result.append(csv_str)
            
            return result
        except Exception as e:
            logger.debug(f"Camelot table extraction failed: {e}")
            return []
    
    def serialize_extraction(self, extraction: Dict) -> str:
        """Serialize extraction result to JSON"""
        return json.dumps(extraction, indent=2, default=str)
    
    def deserialize_extraction(self, json_str: str) -> Dict:
        """Deserialize extraction result from JSON"""
        return json.loads(json_str)
