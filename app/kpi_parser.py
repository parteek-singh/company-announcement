import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .schemas import ExtractionResult, KPIField, FieldEvidence, DocumentType


DATE_PATTERNS = [
    "%d/%m/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%d",
    "%B %d, %Y",
    "%b %d, %Y",
]


def parse_date(text: str) -> Optional[datetime]:
    """Parse date string using multiple formats"""
    text = text.strip()
    for fmt in DATE_PATTERNS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def find_pattern(text: str, pattern: str, flags=0) -> Optional[re.Match]:
    """Find regex pattern in text"""
    return re.search(pattern, text, flags)


def snippet_from_match(text: str, match: re.Match, context: int = 50) -> str:
    """Extract context snippet around match"""
    start = max(match.start() - context, 0)
    end = min(match.end() + context, len(text))
    return text[start:end].strip().replace("\n", " ")


def adjust_confidence(conf: float, penalty: float) -> float:
    """Apply confidence penalty"""
    return max(0.0, conf - penalty)


def detect_document_type(text: str) -> Optional[DocumentType]:
    """Detect document type from text"""
    lower_text = text.lower()
    
    # Keywords for each type
    type_keywords = {
        DocumentType.DIVIDEND: ["dividend", "distribution"],
        DocumentType.SPLIT: ["split", "subdivision"],
        DocumentType.BONUS: ["bonus", "scrip"],
        DocumentType.RIGHTS: ["rights", "entitlements"],
        DocumentType.CAPITAL_RETURN: ["capital", "return", "buyback"],
    }
    
    for dtype, keywords in type_keywords.items():
        for kw in keywords:
            if kw in lower_text:
                return dtype
    
    return None


def parse(raw: Dict[str, Any]) -> ExtractionResult:
    """Parse raw extraction to structured KPI result"""
    pages = raw.get("pages", [])
    full_text = "\n".join(p.get("text", "") for p in pages)
    
    result = ExtractionResult()
    warnings: List[str] = []

    # document type detection
    result.document_type = detect_document_type(full_text)

    # helper to search and assign
    def assign_field(name: str, pattern: str, page_override: Optional[int] = None, 
                    post_process=None, date_field=False) -> KPIField:
        """Search for pattern and assign to field"""
        match = find_pattern(full_text, pattern, flags=re.IGNORECASE)
        field = getattr(result, name)
        
        if match:
            # Get the captured group, or the whole match if no groups
            if match.groups():
                val = match.group(1)
                if val is None:
                    return field
                val = val.strip()
            else:
                val = match.group(0).strip()
            
            original_val = val
            
            if post_process:
                try:
                    val = post_process(val)
                except Exception as e:
                    field.confidence = 0.5
                    val = original_val
            
            field.value = val
            
            # Find page number
            page_num = 1
            search_text = match.group(1) if match.groups() and match.group(1) else match.group(0)
            for i, page in enumerate(pages, 1):
                if search_text in page.get("text", ""):
                    page_num = i
                    break
            
            field.evidence = FieldEvidence(page=page_num, snippet=snippet_from_match(full_text, match))
            
            if field.confidence == 0.0:
                field.confidence = 0.85
            
            if date_field and isinstance(val, datetime):
                field.value = val.date().isoformat()
        
        return field

    # patterns for extraction
    # Company name - look for "Entity name" or "Name of +Entity"
    assign_field("company_name", r"(?:Entity name|Name of \+Entity)\s+([A-Z][^\n]+)")
    
    # Ticker - look for "ASX issuer code" or "ASX +Security Code"
    assign_field("ticker", r"(?:ASX\s+(?:\+)?[Ss]ecurity\s+[Cc]ode|ASX issuer code)\s+([A-Z]{1,5})\b")
    
    # ISIN - look for AU prefix
    assign_field("isin", r"\b(AU[0-9A-Z]{10})\b")

    # dates
    def date_pp(val: str):
        d = parse_date(val)
        if not d:
            raise ValueError("Invalid date format")
        return d

    # Looking for patterns like "Ex Date\n22/4/2026"
    assign_field("ex_date", r"(?:Ex\s*Date|Ex Date)\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", post_process=date_pp, date_field=True)
    assign_field("record_date", r"(?:Record\s*Date|Record Date)\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", post_process=date_pp, date_field=True)
    assign_field("payment_date", r"(?:Payment\s*Date|Payment Date)\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", post_process=date_pp, date_field=True)
    assign_field("announcement_date", r"(?:Date of this announcement|Announcement[- ]?Date)\s+([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})", post_process=date_pp, date_field=True)

    assign_field("dividend_per_share", r"(?:Total dividend|Ordinary Dividend)[^0-9]*(?:per\s+(?:\+)?security)?[^\d]*(AUD\s+)?(\d+\.\d+)")
    
    # Currency - more robust extraction
    for curr in ['AUD', 'USD', 'GBP', 'EUR', 'JPY', 'CNY']:
        curr_match = find_pattern(full_text, rf'{curr}\s*-\s*[^0-9]*(?:Dollar|Pound|Euro|Yen|Yuan)|{curr}(?:\s|$)', flags=re.IGNORECASE)
        if not curr_match:
            curr_match = find_pattern(full_text, rf'\b{curr}\b', flags=re.IGNORECASE)
        if curr_match:
            field = result.currency
            field.value = curr.upper()
            field.evidence = FieldEvidence(page=1, snippet=snippet_from_match(full_text, curr_match))
            field.confidence = 0.95
            break
    
    # avoid matching 'unfranked' by negative lookbehind for 'un'
    assign_field("franking_percentage", r"(?:Percentage of ordinary dividend|Percentage.*(?<!un)franked)\s*([0-9]{1,3})\.?\d*\s*%")
    assign_field("ratio", r"(?:ratio|split)[:\-\s]*(\d+\s*(?:for|:|\s+to\s+)\s*\d+)", page_override=None)

    # Fallbacks for fields that may appear in different sections/lines
    # Dividend per share: look for nearby lines containing AUD amounts labelled as per security or per +security
    if not result.dividend_per_share.value:
        aud_matches = re.findall(r"AUD\s+([0-9]+\.[0-9]+)", full_text)
        if aud_matches:
            # prefer matches that occur near the phrase 'per' or 'per +security' in the text
            for m in aud_matches:
                idx = full_text.find(m)
                window = full_text[max(0, idx-80): idx+80].lower()
                if 'per' in window or 'per +security' in window or 'per security' in window:
                    try:
                        result.dividend_per_share.value = float(m)
                        result.dividend_per_share.confidence = 0.9
                        result.dividend_per_share.evidence = FieldEvidence(page=1, snippet=window.strip())
                        break
                    except Exception:
                        continue
            # if still not set, take first AUD amount as fallback
            if not result.dividend_per_share.value:
                try:
                    result.dividend_per_share.value = float(aud_matches[0])
                    result.dividend_per_share.confidence = 0.7
                    msearch = re.search(r"AUD\s+[0-9]+\.[0-9]+", full_text)
                    result.dividend_per_share.evidence = FieldEvidence(page=1, snippet=snippet_from_match(full_text, msearch))
                except Exception:
                    pass

    # Franking percentage fallback: look for lines containing 'franked' with a percentage
    if not result.franking_percentage.value:
        fmatch = re.search(r"([0-9]+\.?[0-9]*)\s*%\s*(?:franked|franking|percentage)", full_text, flags=re.IGNORECASE)
        if not fmatch:
            fmatch = re.search(r"Percentage of ordinary dividend.*?([0-9]+\.?[0-9]*)\s*%", full_text, flags=re.IGNORECASE | re.DOTALL)
        # additional search: number on its own line preceded by '3A.3' label
        if not fmatch:
            fmatch = re.search(r"3A\.3[^\n]*\n\s*([0-9]+\.?[0-9]*)\s*%", full_text, flags=re.IGNORECASE)
        # fallback generic search (used earlier)
        if not fmatch:
            fmatch = re.search(r"(?:3A\.3[^\n]*\n)?\s*([0-9]+\.?[0-9]*)\s*%", full_text, flags=re.IGNORECASE)
        # ultimate fallback: any number within 100 chars after 3A.3 label
        if not fmatch:
            fmatch = re.search(r"3A\.3[\s\S]{0,100}?([0-9]+\.?[0-9]*)\s*%", full_text, flags=re.IGNORECASE)
        if fmatch:
            try:
                result.franking_percentage.value = float(fmatch.group(1))
                result.franking_percentage.confidence = 0.9
                result.franking_percentage.evidence = FieldEvidence(page=1, snippet=snippet_from_match(full_text, fmatch))
            except Exception:
                pass

    # validation rules
    def to_date(field: KPIField) -> Optional[datetime]:
        """Convert field value to datetime"""
        if field.value:
            try:
                return datetime.fromisoformat(str(field.value))
            except Exception:
                return None
        return None

    ex = to_date(result.ex_date)
    rec = to_date(result.record_date)
    pay = to_date(result.payment_date)
    
    if ex and rec and pay:
        if not (ex <= rec <= pay):
            warnings.append("Date order validation failed: ex_date <= record_date <= payment_date")
            result.ex_date.confidence = adjust_confidence(result.ex_date.confidence, 0.2)
            result.record_date.confidence = adjust_confidence(result.record_date.confidence, 0.2)
            result.payment_date.confidence = adjust_confidence(result.payment_date.confidence, 0.2)

    # isin validation
    if result.isin.value and not re.match(r"^AU[0-9A-Z]{10}$", str(result.isin.value)):
        warnings.append(f"ISIN format invalid: {result.isin.value}")
        result.isin.confidence = adjust_confidence(result.isin.confidence, 0.3)

    # numeric parsing
    for fname in ["dividend_per_share", "franking_percentage"]:
        f = getattr(result, fname)
        if f.value:
            try:
                f.value = float(str(f.value).replace(",", ""))
            except Exception as e:
                warnings.append(f"Numeric parse failed for {fname}: {f.value}")
                f.confidence = adjust_confidence(f.confidence, 0.3)

    # compute overall confidence
    kpi_fields = [
        result.company_name, result.ticker, result.isin,
        result.ex_date, result.record_date, result.payment_date,
        result.dividend_per_share, result.currency, result.franking_percentage, 
        result.ratio, result.announcement_date
    ]
    
    confidences = [f.confidence for f in kpi_fields if f.value is not None]
    if confidences:
        result.overall_confidence = sum(confidences) / len(confidences)
    
    result.warnings = warnings
    return result
