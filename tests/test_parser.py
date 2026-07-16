import pytest
import os
import fitz  # PyMuPDF
from app.services.parser import PDFParserService
from app.utils.helpers import generate_node_hash, normalize_text


@pytest.fixture
def generate_test_pdf(tmp_path):
    """
    Fixture that creates a custom PDF with specific layouts to test the parser.
    """
    def _generator(filename: str, content_list: list):
        pdf_path = tmp_path / filename
        doc = fitz.open()
        page = doc.new_page()
        
        y_offset = 50
        for item in content_list:
            text = item["text"]
            size = item.get("size", 10)
            font = "hebo" if item.get("bold") else "helv"
            
            page.insert_text((50, y_offset), text, fontsize=size, fontname=font)
            y_offset += size + 15
            
        doc.save(str(pdf_path))
        doc.close()
        return str(pdf_path)
    
    return _generator


def test_hash_generation():
    """
    Tests text normalization and SHA256 hash generation helpers.
    """
    title = "  Cuff  Inflation  Protocol  "
    body = "The pump must inflate the cuff to 180 mmHg.\nNew line here."
    
    # Assert whitespace normalization
    assert normalize_text(title) == "cuff inflation protocol"
    assert normalize_text(body) == "the pump must inflate the cuff to 180 mmhg. new line here."

    expected_hash = generate_node_hash(title, body)
    assert len(expected_hash) == 64
    # Re-running returns identical value
    assert generate_node_hash(title, body) == expected_hash


def test_nested_headings_parsing(generate_test_pdf):
    """
    Tests parsing a normal nested document structure (H1 -> H2 -> H3).
    """
    content = [
        {"text": "CardioTrack Manual", "size": 18, "bold": True},
        {"text": "This is general manual introductory text.", "size": 10},
        {"text": "1. Operational Safety Instructions", "size": 14, "bold": True},
        {"text": "Ensure you place the cuff at heart level.", "size": 10},
        {"text": "1.1 Pressure Settings", "size": 12, "bold": True},
        {"text": "Maximum safe pressure limit is set to 290 mmHg.", "size": 10}
    ]
    
    pdf_path = generate_test_pdf("nested_doc.pdf", content)
    parser = PDFParserService()
    nodes = parser.parse_pdf(pdf_path, version_number=1)
    
    # Assert nodes are reconstructed
    # Expected: Root summary node (for intro text), Section 1 node, and Section 1.1 node
    assert len(nodes) >= 2
    
    root_node = next((n for n in nodes if n["title"] == "Document Summary"), None)
    sec1_node = next((n for n in nodes if "1. Operational Safety" in n["title"]), None)
    sec1_1_node = next((n for n in nodes if "1.1 Pressure Settings" in n["title"]), None)
    
    assert sec1_node is not None
    assert sec1_1_node is not None
    
    # Verify hierarchical indentation level
    assert sec1_node["level"] < sec1_1_node["level"]
    # Verify parenting links
    assert sec1_1_node["parent_id"] == sec1_node["id"]
    # Check body accumulation
    assert "cuff at heart level" in normalize_text(sec1_node["body"])
    assert "290 mmhg" in normalize_text(sec1_1_node["body"])


def test_duplicate_headings_handling(generate_test_pdf):
    """
    Tests that duplicate heading names are kept distinct and do not collapse.
    """
    content = [
        {"text": "1. General Overview", "size": 14, "bold": True},
        {"text": "Calibration Specs", "size": 12, "bold": True},
        {"text": "Calibration of pressure valve occurs at 150 mmHg.", "size": 10},
        {"text": "Line of normal body text to increase frequency.", "size": 10},
        {"text": "Another line of body text to establish size 10 as majority.", "size": 10},
        {"text": "2. Maintenance Protocols", "size": 14, "bold": True},
        {"text": "Calibration Specs", "size": 12, "bold": True},
        {"text": "Calibration of exhaust valve occurs at 10 mmHg.", "size": 10},
        {"text": "More normal body text for size 10 frequency.", "size": 10},
        {"text": "Final normal body line in size 10.", "size": 10}
    ]
    
    pdf_path = generate_test_pdf("duplicate_headings.pdf", content)
    parser = PDFParserService()
    nodes = parser.parse_pdf(pdf_path, version_number=1)
    
    calib_nodes = [n for n in nodes if "Calibration Specs" in n["title"]]
    
    # Assert both duplicate titles were parsed as separate entities
    assert len(calib_nodes) == 2
    assert calib_nodes[0]["id"] != calib_nodes[1]["id"]
    
    # Verify they have different parents (Overview vs Maintenance)
    assert calib_nodes[0]["parent_id"] != calib_nodes[1]["parent_id"]


def test_out_of_order_headings_handling(generate_test_pdf):
    """
    Tests that out-of-order levels (e.g. H2 followed by H1) do not break parsing.
    """
    content = [
        {"text": "1.1 Subsection Warning", "size": 12, "bold": True},
        {"text": "Body text under subsection.", "size": 10},
        {"text": "2. Main Heading", "size": 14, "bold": True},
        {"text": "Body text under main heading.", "size": 10}
    ]
    
    pdf_path = generate_test_pdf("out_of_order.pdf", content)
    parser = PDFParserService()
    
    # Should complete without throwing key exceptions or stack errors
    nodes = parser.parse_pdf(pdf_path, version_number=1)
    assert len(nodes) >= 2
