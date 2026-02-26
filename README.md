# Corporate Action Intelligence (CAI) - Offline MVP

Extract KPIs from corporate action PDFs with STRICT JSON output, evidence tracking, and confidence scoring.

## Overview

CAI is a **completely offline** service that extracts key performance indicators (KPIs) from corporate action notices (dividend notices, stock splits, bonus issues, etc.). 

**Key Features:**
- ✅ Offline-only, no cloud APIs (no OpenAI, no online OCR)
- ✅ Handles digital text PDFs, tables, and scanned/image-based PDFs (OCR fallback)
- ✅ Automatic document type detection (DIVIDEND, SPLIT, BONUS, RIGHTS, CAPITAL_RETURN)
- ✅ Strict Pydantic schema validation with field-level confidence scores
- ✅ Evidence tracking: page numbers and text snippets for each extraction
- ✅ Date validation rules (ex_date ≤ record_date ≤ payment_date)
- ✅ ISIN format validation (AU[0-9A-Z]{10})
- ✅ RESTful API with async PDF processing

## Architecture

```
Corporate Action Intelligence (CAI)
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── extractor.py         # PDF text/table/OCR extraction
│   ├── kpi_parser.py        # Rules-based KPI parsing
│   ├── schemas.py           # Pydantic models
│   ├── utils.py             # Storage paths, ID generation
│   └── __init__.py
├── tests/
│   ├── test_kpi_parser.py   # Unit tests with fixtures
│   └── __init__.py
├── storage/
│   ├── pdfs/                # Uploaded PDFs
│   ├── raw/                 # Raw text extractions (JSON)
│   └── results/             # Final KPI results (JSON)
├── requirements.txt
└── README.md
```

## Local Setup
conda create --name <env_name>
conda activate env
conda deactivate
### Prerequisites

- Python 3.11+
- Tesseract OCR (for scanned PDF support)

### 1. Install Tesseract OCR

#### macOS (Homebrew)
```bash
brew install tesseract
```

#### Ubuntu/Debian
```bash
sudo apt-get install tesseract-ocr
```

#### Windows
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
python -c "import fitz; print('PyMuPDF OK')"
python -c "import camelot; print('Camelot OK')"
python -c "import pytesseract; pytesseract.get_tesseract_version(); print('Tesseract OK')"
```

## Running the Service

```bash
# Start FastAPI service (runs on http://localhost:8000)
python3 -m app.main

# Or using uvicorn directly
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The service will:
- Create storage directories if needed
- Listen on `http://localhost:8000`
- Serve interactive docs at `http://localhost:8000/docs`

## API Endpoints

### 1. POST /extract
Upload a PDF and trigger extraction

**Request (with sample resource file):**
```bash
Test all 3 PDFs:
curl -X POST -F "file=@resource/CA3.pdf" http://localhost:8000/extract
curl -X POST -F "file=@resource/CA2.pdf" http://localhost:8000/extract
curl -X POST -F "file=@resource/CA1.pdf" http://localhost:8000/extract

curl -X POST -F "file=@resource/CA3.pdf" http://localhost:8000/extract

{
  "doc_id": "abc123...",
  "status": "completed",
  "message": "PDF extraction completed successfully"
}

curl http://localhost:8000/result/abc123...
```

**Response (201):**
```json
{
  "doc_id": "a1b2c3d4e5f6...",
  "status": "completed",
  "message": "PDF extraction completed successfully"
}
```

### 2. GET /result/{doc_id}
Retrieve final extraction result with KPIs, confidence, and evidence

**Request:**
```bash
curl http://localhost:8000/result/a1b2c3d4e5f6...
```

**Response (200):**
```json
{
  "doc_id": "a1b2c3d4e5f6...",
  "document_type": "DIVIDEND",
  "company_name": {
    "value": "BHP Group Limited",
    "confidence": 0.95,
    "evidence": [
      {
        "page": 1,
        "snippet": "...BHP Group Limited hereby gives notice of dividend..."
      }
    ]
  },
  "ticker": {
    "value": "BHP",
    "confidence": 0.90,
    "evidence": [
      {
        "page": 1,
        "snippet": "...ASX Code: BHP..."
      }
    ]
  },
  "isin": {
    "value": "AU0000014844",
    "confidence": 0.95,
    "evidence": null
  },
  "ex_date": {
    "value": "2026-03-15",
    "confidence": 0.92,
    "evidence": [
      {
        "page": 1,
        "snippet": "...Ex-Date: 15 March 2026..."
      }
    ]
  },
  "record_date": {
    "value": "2026-03-17",
    "confidence": 0.92,
    "evidence": [
      {
        "page": 1,
        "snippet": "...Record Date: 17 March 2026..."
      }
    ]
  },
  "payment_date": {
    "value": "2026-04-01",
    "confidence": 0.92,
    "evidence": [
      {
        "page": 1,
        "snippet": "...Payment Date: 1 April 2026..."
      }
    ]
  },
  "dividend_per_share": {
    "value": 0.45,
    "confidence": 0.88,
    "evidence": [
      {
        "page": 1,
        "snippet": "...Dividend: $0.45 per share..."
      }
    ]
  },
  "currency": {
    "value": "AUD",
    "confidence": 0.95,
    "evidence": null
  },
  "franking_percentage": {
    "value": 100.0,
    "confidence": 0.90,
    "evidence": [
      {
        "page": 1,
        "snippet": "...100% franked..."
      }
    ]
  },
  "ratio": {
    "value": null,
    "confidence": 0.0,
    "evidence": null
  },
  "announcement_date": {
    "value": "2026-02-15",
    "confidence": 0.85,
    "evidence": null
  },
  "overall_confidence": 0.91,
  "warnings": []
}
```

### 3. GET /raw/{doc_id}
Retrieve raw text extraction (debug endpoint)

**Request:**
```bash
curl http://localhost:8000/raw/a1b2c3d4e5f6...
```

**Response:**
```json
{
  "doc_id": "a1b2c3d4e5f6...",
  "pages": [
    {
      "page_num": 1,
      "text": "BHP Group Limited hereby gives notice...",
      "tables": [],
      "ocr_used": false
    }
  ],
  "extraction_timestamp": "2026-02-26T10:30:45.123456",
  "ocr_used_pages": []
}
```

### 4. GET /health
Health check endpoint

```bash
curl http://localhost:8000/health
```

### 5. GET /list
List all processed documents

```bash
curl http://localhost:8000/list
```

### 6. GET /download/{doc_id}
Download original uploaded PDF

```bash
curl -o result.pdf http://localhost:8000/download/a1b2c3d4e5f6...
```

## Extraction Rules

### Document Type Detection
Keyword-based detection among:
- `DIVIDEND` → "dividend", "distribution"
- `SPLIT` → "split", "subdivision"
- `BONUS` → "bonus", "scrip"
- `RIGHTS` → "rights", "entitlements"
- `CAPITAL_RETURN` → "capital", "return", "buyback"

### Field Extraction Patterns

| Field | Pattern | Example |
|-------|---------|---------|
| company_name | `Company:`/`Issuer:` | BHP Group Limited |
| ticker | `ASX Code:` | BHP |
| isin | `AU[0-9A-Z]{10}` | AU0000014844 |
| ex_date | `Ex-Date:` | 15 March 2026 |
| record_date | `Record Date:` | 17 March 2026 |
| payment_date | `Payment Date:` | 1 April 2026 |
| dividend_per_share | `Dividend per Share:` | $0.45 |
| currency | `AUD`/`USD`/etc | AUD |
| franking_percentage | `\d+% franked` | 100% |
| ratio | `ratio: X for Y` | 1 for 2 |

### Validation Rules

1. **Date Order**: `ex_date ≤ record_date ≤ payment_date` (if all present)
   - Failure → Warning added, confidence reduced by 0.2

2. **ISIN Format**: `^AU[0-9A-Z]{10}$`
   - Failure → Warning added, confidence reduced by 0.3

3. **Numeric Parsing**: `dividend_per_share`, `franking_percentage`
   - Failure → Warning added, confidence reduced by 0.3

4. **Confidence Penalties**:
   - Failed date parsing: -0.2
   - Failed ISIN validation: -0.3
   - Failed numeric parsing: -0.3

### OCR Fallback

If extracted text < 50 characters (indicating scanned/image-based page):
1. Tesseract OCR applied to 2x-zoom page rendering
2. OCR result replaces extracted text
3. Page marked in `ocr_used_pages` array

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_kpi_parser.py::test_dividend_extraction -v

# Run with coverage
pytest tests/ --cov=app
```

## Sample Resource Files

Test the service using sample corporate action documents:

```bash
# Start the service
python -m app.main

# In another terminal, test with PDF files:

# Dividend notice extraction
curl -X POST -F "file=@resources/sample-dividend-notice.pdf" http://localhost:8000/extract
# Returns: {"doc_id": "xxx", "status": "completed", ...}
# Then retrieve result:
# curl http://localhost:8000/result/xxx

# Stock split extraction  
curl -X POST -F "file=@resources/sample-stock-split.txt" http://localhost:8000/extract
# Returns: {"doc_id": "yyy", "status": "completed", ...}
# Then retrieve result:
# curl http://localhost:8000/result/yyy

# View all processed documents
curl http://localhost:8000/list

# Download original file
curl -o downloaded.txt http://localhost:8000/download/xxx
```

### Test Fixtures

Two text-based fixtures included (no real PDFs required):

**Fixture 1: Dividend Notice**
```
BHP Group Limited
ASX Code: BHP
ISIN: AU0000014844

Ex-Date: 15 March 2026
Record Date: 17 March 2026
Payment Date: 1 April 2026

Dividend: $0.45 per share
100% franked
```

**Fixture 2: Stock Split**
```
Rio Tinto PLC
ASX Code: RIO
ISIN: AU96004458985

Stock Split Ratio: 1 for 2
Ex-Date: 1 May 2026
Record Date: 5 May 2026
Implementation Date: 15 May 2026
```

## Confidence Scoring

Each extracted field receives a confidence score (0.0-1.0) based on:
- **Pattern match quality**: 0.85-0.95 for clear matches
- **Post-processing success**: -0.3-0.5 penalty for parsing errors
- **Validation failures**: -0.2-0.3 penalty per failed rule

**Overall Confidence** = Average of all field confidences (only non-null fields counted)

Example:
- Well-formed dividend notice: 0.90-0.95
- Scanned/OCR'd page: 0.70-0.85
- Damaged/incomplete document: 0.50-0.70

## Storage

All files stored locally (no cloud):

```
storage/
├── pdfs/
│   └── {doc_id}.pdf                 # Original uploaded PDF
├── raw/
│   └── {doc_id}.json                # Raw text extraction + OCR markers
└── results/
    └── {doc_id}.json                # Final KPI result with confidence
```

Example storage paths:
```
storage/pdfs/a1b2c3d4e5f6.pdf
storage/raw/a1b2c3d4e5f6.json
storage/results/a1b2c3d4e5f6.json
```

## Error Handling

API returns appropriate HTTP status codes:

| Status | Scenario |
|--------|----------|
| 200 | Success (GET result/raw) |
| 201 | Created (POST extract) |
| 400 | Bad request (invalid file type) |
| 404 | Document not found |
| 500 | Server error (extraction failed, etc.) |

Error response format:
```json
{
  "detail": "Error description here"
}
```

## Dependencies

### Core
- **FastAPI** (0.104.1) - REST framework
- **Uvicorn** (0.24.0) - ASGI server
- **Pydantic** (2.5.0) - Data validation

### PDF Processing
- **PyMuPDF/fitz** (1.23.8) - Text/page extraction
- **Camelot** (0.11.0) - Table extraction (lattice + stream)
- **Pillow** (10.1.0) - Image processing

### OCR
- **pytesseract** (0.3.10) - Tesseract wrapper
- **Tesseract** (system) - OCR engine (install separately)

### Testing
- **pytest** (7.4.3) - Test framework
- **pytest-asyncio** (0.21.1) - Async test support

## Troubleshooting

### "Tesseract not found" error
```bash
# macOS
brew install tesseract

# Set tesseract path (if installed in non-standard location)
export TESSERACT_CMD=/usr/local/bin/tesseract
```

### "No module named fitz"
```bash
pip install PyMuPDF
```

### "Camelot failed to extract tables"
- Camelot requires `ghostscript` for some operations
- macOS: `brew install ghostscript`
- Ubuntu: `sudo apt-get install ghostscript`

### PDF upload fails with large files
- Current implementation loads entire PDF into memory
- For files > 100MB, consider streaming/chunking

### Low confidence scores on certain PDFs
- Check OCR fallback was applied (check `ocr_used_pages`)
- Verify document format matches expected corporate action notice
- Scanned/compressed documents may have lower confidence

## Performance

### Typical Extraction Times
- **Digital text PDF** (1-5 pages): 0.5-1 second
- **PDF with tables** (1-5 pages): 1-2 seconds  
- **Scanned PDF** (1-5 pages, OCR): 3-8 seconds (OCR overhead)

### Storage Requirements
- **Average PDF**: 500KB-5MB
- **Raw extraction JSON**: 50-500KB
- **Result JSON**: 5-20KB

## Production Considerations

For production deployments:

1. **Async Processing**: Use Celery/RQ for long-running extractions
2. **Database**: Replace filesystem storage with PostgreSQL
3. **Caching**: Add Redis for frequently accessed results
4. **Rate Limiting**: Add per-IP request throttling
5. **Auth**: Implement API key or OAuth2 authentication
6. **Monitoring**: Add Prometheus metrics and error logging
7. **Scale**: Use Docker + Kubernetes for multi-instance deployment

Example Docker setup:
```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y tesseract-ocr ghostscript
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app app
CMD ["python", "-m", "app.main"]
```

## License

Offline MVP - Use locally/internally only.

---

**Questions?** Check the test fixtures in `tests/test_kpi_parser.py` for expected input/output format.
