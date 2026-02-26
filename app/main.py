"""
FastAPI service for Corporate Action Intelligence (CAI)
Offline-only MVP for KPI extraction from corporate action PDFs
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn

from app.extractor import PDFExtractor
from app.kpi_parser import parse
from app.schemas import ExtractionResult, RawExtraction
from app.utils import (
    ensure_storage_dirs,
    generate_doc_id,
    pdf_path,
    raw_path,
    result_path,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Corporate Action Intelligence (CAI)",
    description="Offline-only MVP for extracting KPIs from corporate action notices",
    version="1.0.0",
)

# Templates for UI
templates = Jinja2Templates(directory="templates")

# Initialize storage
ensure_storage_dirs()
extractor = PDFExtractor()


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Corporate Action Intelligence (CAI)",
        "version": "1.0.0",
        "mode": "offline",
    }


def scan_folder(folder: str):
    """Return list of pdf files under folder"""
    result = []
    if not os.path.isdir(folder):
        return result
    for root, dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith('.pdf'):
                path = os.path.join(root, name)
                try:
                    size = os.path.getsize(path)
                except Exception:
                    size = 0
                result.append({"path": path, "size": size})
    return result


def detect_dividend_type_from_text(text: str) -> Optional[str]:
    """Infer dividend type from extracted document text."""
    if not text:
        return None

    lower = text.lower()

    # Prefer explicit ASX section headers when present.
    asx_part_patterns = [
        (r"part\s+3a\s*-\s*ordinary\s+dividend", "ORDINARY"),
        (r"part\s+3b\s*-\s*interim\s+dividend", "INTERIM"),
        (r"part\s+3c\s*-\s*special\s+dividend", "SPECIAL"),
        (r"part\s+3d\s*-\s*final\s+dividend", "FINAL"),
    ]
    for pattern, value in asx_part_patterns:
        if re.search(pattern, lower):
            return value

    # Try to read explicit "Type of dividend/distribution" value blocks.
    explicit = re.search(
        r"type of dividend/distribution\s+([a-z][a-z \-/]{2,40})",
        lower,
    )
    if explicit:
        raw_type = explicit.group(1).strip()
        if "ordinary" in raw_type:
            return "ORDINARY"
        if "interim" in raw_type:
            return "INTERIM"
        if "final" in raw_type:
            return "FINAL"
        if "special" in raw_type:
            return "SPECIAL"

    # Broad fallbacks.
    if "interim" in lower:
        return "INTERIM"
    if "final" in lower:
        return "FINAL"
    if "special" in lower:
        return "SPECIAL"
    if "ordinary dividend" in lower or "ordinary dividend/distribution" in lower:
        return "ORDINARY"
    return None


@app.get("/browse", tags=["System"], response_class=HTMLResponse)
def browse_get(request: Request):
    """Render folder scan form"""
    return templates.TemplateResponse("browse.html", {"request": request})


@app.post("/browse", tags=["System"], response_class=HTMLResponse)
def browse_post(request: Request, path: str = Form(...)):
    """Handle form submission, scan and display results"""
    files = scan_folder(path)
    # try to extract KPIs for each PDF file (non-blocking; failures are captured)
    detailed = []
    import shutil
    from app.utils import pdf_path, raw_path, result_path

    for f in files:
        entry = f.copy()
        doc_id = generate_doc_id()
        entry["doc_id"] = doc_id
        # copy the PDF into storage for reference
        try:
            shutil.copy(f["path"], pdf_path(doc_id))
        except Exception:
            pass
        try:
            extraction = extractor.extract_from_pdf(f["path"])
            extraction["doc_id"] = doc_id
            # capture full text for later heuristics
            pages = extraction.get("pages", [])
            entry["full_text"] = "\n".join(p.get("text", "") for p in pages)

            kpi = parse(extraction)
            kpi.doc_id = doc_id
            entry["kpi"] = kpi.model_dump()
            # persist raw and result as /extract would have done
            with open(raw_path(doc_id), 'w') as rf:
                rf.write(extractor.serialize_extraction(extraction))
            with open(result_path(doc_id), 'w') as rf:
                rf.write(kpi.model_dump_json(indent=2))
        except Exception as e:
            entry["error"] = str(e)
        detailed.append(entry)
    json_output = json.dumps(detailed, indent=2)
    # create version without evidence for client consumption
    def strip_evidence(obj):
        if isinstance(obj, dict):
            return {k: strip_evidence(v) for k, v in obj.items() if k != "evidence"}
        elif isinstance(obj, list):
            return [strip_evidence(v) for v in obj]
        else:
            return obj
    clean = strip_evidence(detailed)

    # additionally create a nicely structured payload per document
    def make_struct(doc):
        k = doc.get("kpi") or {}
        text = doc.get("full_text", "")
        div_type = detect_dividend_type_from_text(text)
        return {
            "document_id": doc.get("doc_id"),
            "document_type": k.get("document_type"),
            "company": {
                "name": k.get("company_name", {}).get("value"),
                "ticker": k.get("ticker", {}).get("value"),
                "isin": k.get("isin", {}).get("value"),
            },
            "action_details": {
                "dividend_type": div_type,
                "dividend_per_share": k.get("dividend_per_share", {}).get("value"),
                "currency": k.get("currency", {}).get("value"),
                "franking_percentage": k.get("franking_percentage", {}).get("value"),
            },
            "important_dates": {
                "announcement_date": k.get("announcement_date", {}).get("value"),
                "ex_date": k.get("ex_date", {}).get("value"),
                "record_date": k.get("record_date", {}).get("value"),
                "payment_date": k.get("payment_date", {}).get("value"),
            },
        }
    structured = [make_struct(d) for d in clean]
    json_structured = json.dumps(structured, indent=2)

    return templates.TemplateResponse(
        "browse.html",
        {
            "request": request,
            "files": detailed,
            "json_output": json_output,
            "json_structured": json_structured,
            "path": path,
        },
    )


@app.post("/extract", tags=["Extraction"])
async def extract_pdf(file: UploadFile = File(...)):
    """
    Upload PDF and trigger extraction
    
    Returns doc_id immediately (async processing)
    
    Response:
        {
            "doc_id": "unique-document-id",
            "status": "processing",
            "message": "PDF queued for extraction"
        }
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files accepted")
    
    doc_id = generate_doc_id()
    pdf_file_path = pdf_path(doc_id)
    
    try:
        # Save uploaded PDF
        content = await file.read()
        with open(pdf_file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"PDF uploaded: {doc_id}, size={len(content)} bytes")
        
        # Start extraction (synchronous for MVP, can be async with Celery/Queue)
        try:
            extraction_result = extractor.extract_from_pdf(pdf_file_path)
            extraction_result["doc_id"] = doc_id
            
            # Save raw extraction
            raw_file_path = raw_path(doc_id)
            with open(raw_file_path, 'w') as f:
                f.write(extractor.serialize_extraction(extraction_result))
            
            # Parse to KPIs
            kpi_result = parse(extraction_result)
            kpi_result.doc_id = doc_id
            
            # Save result
            result_file_path = result_path(doc_id)
            with open(result_file_path, 'w') as f:
                f.write(kpi_result.model_dump_json(indent=2))
            
            logger.info(f"Extraction complete: {doc_id}")
            
            return {
                "doc_id": doc_id,
                "status": "completed",
                "message": "PDF extraction completed successfully"
            }
        
        except Exception as e:
            logger.error(f"Extraction failed for {doc_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Extraction failed: {str(e)}"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/result/{doc_id}", tags=["Results"])
def get_result(doc_id: str):
    """
    Retrieve extraction result for a document
    
    Returns:
        {
            "doc_id": str,
            "document_type": str or null,
            "company_name": {...},
            "ticker": {...},
            ... (all extracted fields with confidence and evidence),
            "overall_confidence": float,
            "warnings": List[str]
        }
    """
    result_file = result_path(doc_id)
    
    if not os.path.exists(result_file):
        raise HTTPException(
            status_code=404,
            detail=f"No extraction result found for doc_id: {doc_id}"
        )
    
    try:
        with open(result_file, 'r') as f:
            result_json = json.load(f)
        return result_json
    except Exception as e:
        logger.error(f"Failed to read result {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read result")


@app.get("/raw/{doc_id}", tags=["Results"])
def get_raw_extraction(doc_id: str):
    """
    Retrieve raw text extraction for a document (debug endpoint)
    
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
    raw_file = raw_path(doc_id)
    
    if not os.path.exists(raw_file):
        raise HTTPException(
            status_code=404,
            detail=f"No raw extraction found for doc_id: {doc_id}"
        )
    
    try:
        with open(raw_file, 'r') as f:
            raw_json = json.load(f)
        return raw_json
    except Exception as e:
        logger.error(f"Failed to read raw extraction {doc_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read raw extraction")


@app.get("/download/{doc_id}", tags=["Files"])
def download_pdf(doc_id: str):
    """Download original uploaded PDF"""
    pdf_file = pdf_path(doc_id)
    
    if not os.path.exists(pdf_file):
        raise HTTPException(
            status_code=404,
            detail=f"PDF not found for doc_id: {doc_id}"
        )
    
    return FileResponse(
        path=pdf_file,
        filename=f"{doc_id}.pdf",
        media_type="application/pdf"
    )


@app.get("/list", tags=["System"])
def list_documents():
    """List all processed documents"""
    from app.utils import RESULT_DIR
    
    docs = []
    try:
        for filename in os.listdir(RESULT_DIR):
            if filename.endswith('.json'):
                doc_id = filename[:-5]
                result_file = result_path(doc_id)
                with open(result_file, 'r') as f:
                    result = json.load(f)
                docs.append({
                    "doc_id": doc_id,
                    "document_type": result.get("document_type"),
                    "company_name": result.get("company_name", {}).get("value"),
                    "overall_confidence": result.get("overall_confidence", 0)
                })
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
    
    return {"documents": docs, "count": len(docs)}


def main():
    """Run the FastAPI service"""
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )


if __name__ == "__main__":
    main()
