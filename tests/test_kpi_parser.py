"""
Unit tests for KPI parser with text-based fixtures
No real PDFs required - uses example text strings
"""

import pytest
from app.kpi_parser import parse, parse_date, detect_document_type
from app.schemas import DocumentType


class TestDateParsing:
    """Test date parsing with multiple formats"""
    
    def test_parse_date_dmy_long(self):
        result = parse_date("15 March 2026")
        assert result is not None
        assert result.day == 15
        assert result.month == 3
        assert result.year == 2026
    
    def test_parse_date_dmy_short(self):
        result = parse_date("15 Mar 2026")
        assert result is not None
        assert result.day == 15
        assert result.month == 3
    
    def test_parse_date_iso(self):
        result = parse_date("2026-03-15")
        assert result is not None
        assert result.year == 2026
        assert result.month == 3
        assert result.day == 15
    
    def test_parse_date_invalid(self):
        result = parse_date("not a date")
        assert result is None


class TestDocumentTypeDetection:
    """Test document type detection"""
    
    def test_detect_dividend(self):
        text = "This is a dividend notice. Dividend per share: $0.45"
        result = detect_document_type(text)
        assert result == DocumentType.DIVIDEND
    
    def test_detect_split(self):
        text = "Stock split announcement. Split ratio 1 for 2"
        result = detect_document_type(text)
        assert result == DocumentType.SPLIT
    
    def test_detect_bonus(self):
        text = "Bonus issue notice. Bonus entitlement 1 for 5"
        result = detect_document_type(text)
        assert result == DocumentType.BONUS
    
    def test_detect_rights(self):
        text = "Rights issue announcement. Rights entitlements offered"
        result = detect_document_type(text)
        assert result == DocumentType.RIGHTS
    
    def test_detect_capital_return(self):
        text = "Capital return to shareholders"
        result = detect_document_type(text)
        assert result == DocumentType.CAPITAL_RETURN
    
    def test_detect_none(self):
        text = "Some random corporate document"
        result = detect_document_type(text)
        assert result is None


class TestDividendExtraction:
    """Test KPI extraction from dividend notice fixture"""
    
    @pytest.fixture
    def dividend_notice_fixture(self):
        """Dividend notice text fixture"""
        return {
            "pages": [
                {
                    "text": """
BHP Group Limited
ABN 12 345 678 901
ASX Code: BHP
ISIN: AU0000014844

Notice of Dividend

The Board of BHP Group Limited hereby gives notice that a fully 
paid ordinary dividend of $0.45 per share has been declared.

Announcement Date: 15 February 2026
Ex-Date: 15 March 2026
Record Date: 17 March 2026
Payment Date: 1 April 2026

Franking Information:
The dividend is 100% franked.
Franking tax credit: $0.1929 per share

Currency: AUD

For further information, please contact our Investor Relations team.
                    """
                }
            ]
        }
    
    def test_extract_company_name(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.company_name.value == "BHP Group Limited"
        assert result.company_name.confidence > 0.7
    
    def test_extract_ticker(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.ticker.value == "BHP"
        assert result.ticker.confidence > 0.7
    
    def test_extract_isin(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.isin.value == "AU0000014844"
        assert result.isin.confidence > 0.7
    
    def test_extract_dividend_per_share(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.dividend_per_share.value == 0.45
        assert result.dividend_per_share.confidence > 0.7
    
    def test_extract_dates(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        
        assert result.announcement_date.value == "2026-02-15"
        assert result.ex_date.value == "2026-03-15"
        assert result.record_date.value == "2026-03-17"
        assert result.payment_date.value == "2026-04-01"
    
    def test_date_order_validation(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        # Date order should be correct: ex < record < payment
        assert len(result.warnings) == 0
    
    def test_extract_franking(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.franking_percentage.value == 100.0
        assert result.franking_percentage.confidence > 0.7
    
    def test_extract_currency(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.currency.value == "AUD"
    
    def test_document_type_dividend(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.document_type == DocumentType.DIVIDEND
    
    def test_overall_confidence_dividend(self, dividend_notice_fixture):
        result = parse(dividend_notice_fixture)
        assert result.overall_confidence > 0.75


class TestStockSplitExtraction:
    """Test KPI extraction from stock split fixture"""
    
    @pytest.fixture
    def stock_split_fixture(self):
        """Stock split notice text fixture"""
        return {
            "pages": [
                {
                    "text": """
Rio Tinto PLC
ASX Code: RIO
ISIN: AU96004458985

Stock Split Announcement

Rio Tinto announces a share subdivision (split) on the following basis:

Subdivision Ratio: 1 share for every 2 held

Ex-Date: 1 May 2026
Record Date: 5 May 2026
Implementation Date: 15 May 2026

The new shares will be issued and trading will commence on 
15 May 2026. All existing shareholders will receive the 
additional shares automatically.

Currency: AUD
                    """
                }
            ]
        }
    
    def test_extract_company_name_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert "Rio Tinto" in str(result.company_name.value)
    
    def test_extract_ticker_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.ticker.value == "RIO"
    
    def test_extract_isin_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.isin.value == "AU96004458985"
    
    def test_extract_split_ratio(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.ratio.value is not None
        assert "1" in str(result.ratio.value)
        assert "2" in str(result.ratio.value)
    
    def test_extract_dates_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.ex_date.value == "2026-05-01"
        assert result.record_date.value == "2026-05-05"
    
    def test_document_type_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.document_type == DocumentType.SPLIT
    
    def test_overall_confidence_split(self, stock_split_fixture):
        result = parse(stock_split_fixture)
        assert result.overall_confidence > 0.60


class TestValidationRules:
    """Test validation and error handling"""
    
    @pytest.fixture
    def invalid_date_order_fixture(self):
        """Fixture with invalid date order"""
        return {
            "pages": [
                {
                    "text": """
Test Company
ASX Code: TST
ISIN: AU1234567890

Ex-Date: 1 April 2026
Record Date: 17 March 2026
Payment Date: 15 May 2026

Dividend: $0.50 per share
                    """
                }
            ]
        }
    
    @pytest.fixture
    def invalid_isin_fixture(self):
        """Fixture with invalid ISIN"""
        return {
            "pages": [
                {
                    "text": """
Test Company
ISIN: INVALID123
Dividend: $0.50
                    """
                }
            ]
        }
    
    def test_date_order_validation_fails(self, invalid_date_order_fixture):
        result = parse(invalid_date_order_fixture)
        # Should have warning about date order
        assert any("Date order" in w for w in result.warnings)
        # Confidence should be reduced
        assert result.ex_date.confidence < 0.9 or result.record_date.confidence < 0.9
    
    def test_isin_validation_fails(self, invalid_isin_fixture):
        result = parse(invalid_isin_fixture)
        # Should have warning about ISIN format
        assert any("ISIN" in w for w in result.warnings)
        assert result.isin.confidence < 0.9
    
    def test_evidence_tracking(self, dividend_notice_fixture):
        """Test that evidence is tracked for extracted fields"""
        from app.kpi_parser import parse
        
        raw = {
            "pages": [
                {
                    "text": """
BHP Group Limited
Ex-Date: 15 March 2026
Dividend: $0.45 per share
                    """
                }
            ]
        }
        
        result = parse(raw)
        
        # Evidence should be present for matched fields
        if result.company_name.value:
            assert result.company_name.evidence is not None
        if result.ex_date.value:
            assert result.ex_date.evidence is not None


class TestEdgeCases:
    """Test edge cases and malformed input"""
    
    def test_empty_fixture(self):
        result = parse({"pages": [{"text": ""}]})
        assert result.company_name.value is None
        assert result.overall_confidence == 0.0
    
    def test_partial_data(self):
        raw = {"pages": [{"text": "BHP Group Limited\nDividend: $0.50"}]}
        result = parse(raw)
        assert result.company_name.value == "BHP Group Limited"
        assert result.dividend_per_share.value == 0.50
        assert result.ticker.value is None
    
    def test_multiple_pages(self):
        raw = {
            "pages": [
                {"text": "BHP Group Limited\nASX Code: BHP"},
                {"text": "Dividend: $0.45 per share\nEx-Date: 15 March 2026"}
            ]
        }
        result = parse(raw)
        assert result.company_name.value == "BHP Group Limited"
        assert result.dividend_per_share.value == 0.45
    
    def test_malformed_currency(self):
        raw = {
            "pages": [
                {"text": "Dividend: $0.45 per share\nCurrency: INVALID"}
            ]
        }
        result = parse(raw)
        # Should still extract dividend even with invalid currency
        assert result.dividend_per_share.value == 0.45


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
