import fitz  # PyMuPDF
import pdfplumber
import uuid
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from app.utils.helpers import generate_node_hash

logger = logging.getLogger("app.services.parser")


class PDFParserService:
    def __init__(self):
        pass

    def parse_pdf(self, file_path: str, version_number: int) -> List[Dict[str, Any]]:
        """
        Parses a PDF file from the local file system.
        Returns a flat list of node dictionaries representing the reconstructed hierarchy.
        Each node contains children references (flat model references parent_id).
        """
        logger.info(f"Starting parsing of PDF: {file_path}")
        
        # Step 1: Extract font size distribution and analyze headings
        font_sizes = self._analyze_font_sizes(file_path)
        body_font = self._determine_body_font_size(font_sizes)
        logger.info(f"Determined body font size: {body_font}pt")

        # Step 2: Parse page by page, combining PyMuPDF layout and pdfplumber tables
        raw_elements = []
        with pdfplumber.open(file_path) as pdf_plumber_doc:
            fitz_doc = fitz.open(file_path)
            
            for page_num in range(len(fitz_doc)):
                fitz_page = fitz_doc[page_num]
                plumber_page = pdf_plumber_doc.pages[page_num]
                
                # Extract tables with their bounding boxes
                tables = self._extract_tables_with_bboxes(plumber_page)
                
                # Extract text spans using fitz
                page_spans = self._extract_page_spans(fitz_page)
                
                # Filter spans that are inside table bounding boxes
                non_table_spans = self._filter_spans_in_tables(page_spans, tables, fitz_page.rect.height)
                
                # Group remaining spans into logical paragraphs/headings
                page_elements = self._group_spans_into_elements(non_table_spans, body_font, page_num + 1)
                
                # Merge tables in their correct vertical order on the page
                page_elements = self._merge_tables_into_elements(page_elements, tables, page_num + 1)
                
                raw_elements.extend(page_elements)

            fitz_doc.close()

        # Step 3: Reconstruct hierarchy tree from elements
        nodes = self._reconstruct_hierarchy(raw_elements, version_number)
        logger.info(f"Completed parsing PDF. Reconstructed {len(nodes)} document nodes.")
        return nodes

    def _analyze_font_sizes(self, file_path: str) -> List[float]:
        """
        Scan all spans in the PDF to build a list of all distinct font sizes.
        """
        doc = fitz.open(file_path)
        sizes = []
        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if b.get("type") == 0:  # Text block
                    for line in b["lines"]:
                        for span in line["spans"]:
                            # Keep size rounded to 1 decimal place
                            sizes.append(round(span["size"], 1))
        doc.close()
        return sizes

    def _determine_body_font_size(self, font_sizes: List[float]) -> float:
        """
        Identifies the body text font size as the most common font size.
        Defaults to 10.0 if not detectable.
        """
        if not font_sizes:
            return 10.0
        from collections import Counter
        counter = Counter(font_sizes)
        body_size, _ = counter.most_common(1)[0]
        return body_size

    def _extract_tables_with_bboxes(self, plumber_page) -> List[Dict[str, Any]]:
        """
        Extract tables and their vertical bounding boxes using pdfplumber.
        """
        tables = []
        found_tables = plumber_page.find_tables()
        for tbl in found_tables:
            # bbox is (x0, top, x1, bottom)
            bbox = tbl.bbox
            # Get table content as a matrix of cells
            table_data = tbl.extract()
            # Convert matrix to a Markdown table representation
            markdown_table = self._format_markdown_table(table_data)
            tables.append({
                "bbox": bbox,
                "top": bbox[1],
                "bottom": bbox[3],
                "body": markdown_table,
                "type": "table"
            })
        return tables

    def _format_markdown_table(self, table_data: List[List[Optional[str]]]) -> str:
        """
        Formats raw double-nested lists into a tidy GFM markdown table.
        """
        if not table_data or not table_data[0]:
            return ""
        
        # Clean cell contents (remove newlines, replace None with empty string)
        cleaned_data = []
        for row in table_data:
            cleaned_row = []
            for cell in row:
                if cell is None:
                    cleaned_row.append("")
                else:
                    cleaned_row.append(cell.replace("\n", " ").strip())
            cleaned_data.append(cleaned_row)

        headers = cleaned_data[0]
        rows = cleaned_data[1:]
        
        markdown = "| " + " | ".join(headers) + " |\n"
        markdown += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        for row in rows:
            markdown += "| " + " | ".join(row) + " |\n"
        return markdown

    def _extract_page_spans(self, fitz_page) -> List[Dict[str, Any]]:
        """
        Extracts raw text spans from PyMuPDF page dictionary.
        """
        spans = []
        blocks = fitz_page.get_text("dict")["blocks"]
        for b in blocks:
            if b.get("type") == 0:  # Text block
                for line in b["lines"]:
                    for span in line["spans"]:
                        spans.append({
                            "text": span["text"],
                            "size": round(span["size"], 1),
                            "font": span["font"],
                            "bbox": span["bbox"],  # (x0, y0, x1, y1)
                            "y": span["bbox"][1]  # vertical coordinate
                        })
        # Sort spans by vertical coordinate primarily, and horizontal coordinate secondarily
        spans.sort(key=lambda s: (s["y"], s["bbox"][0]))
        return spans

    def _filter_spans_in_tables(self, spans: List[Dict[str, Any]], tables: List[Dict[str, Any]], page_height: float) -> List[Dict[str, Any]]:
        """
        Remove text spans that overlap with tables to avoid double extraction or scrambling.
        """
        filtered = []
        for span in spans:
            x0, y0, x1, y1 = span["bbox"]
            in_table = False
            for table in tables:
                tx0, ty0, tx1, ty1 = table["bbox"]
                # Check if the vertical center of the span falls within the table boundaries
                span_center_y = (y0 + y1) / 2
                span_center_x = (x0 + x1) / 2
                
                # Check bounding box overlap
                if (tx0 <= span_center_x <= tx1) and (ty0 <= span_center_y <= ty1):
                    in_table = True
                    break
            if not in_table:
                filtered.append(span)
        return filtered

    def _group_spans_into_elements(self, spans: List[Dict[str, Any]], body_font: float, page_num: int) -> List[Dict[str, Any]]:
        """
        Groups sequential spans of text into blocks and determines if they are headings or paragraph text.
        """
        elements = []
        if not spans:
            return elements

        current_element = {
            "text": "",
            "size": spans[0]["size"],
            "font": spans[0]["font"],
            "y_start": spans[0]["y"],
            "y_end": spans[0]["bbox"][3],
            "is_heading": False,
            "level": -1,
            "page_number": page_num,
            "type": "text"
        }

        for span in spans:
            # If the current span is on a new line or has a significantly different font size, flush the current element
            font_size_diff = abs(span["size"] - current_element["size"]) > 1.0
            new_line = (span["y"] - current_element["y_end"]) > 8.0  # simple threshold for a line break
            
            if (font_size_diff or new_line) and current_element["text"].strip():
                # Process the flushed element
                self._evaluate_element_role(current_element, body_font)
                elements.append(current_element)
                
                # Start new element
                current_element = {
                    "text": span["text"],
                    "size": span["size"],
                    "font": span["font"],
                    "y_start": span["y"],
                    "y_end": span["bbox"][3],
                    "is_heading": False,
                    "level": -1,
                    "page_number": page_num,
                    "type": "text"
                }
            else:
                # Append to current element
                if current_element["text"]:
                    # Check if space is needed
                    if current_element["text"].endswith("-"):
                        # Hyphenated word break
                        current_element["text"] = current_element["text"][:-1] + span["text"]
                    else:
                        current_element["text"] += " " + span["text"]
                else:
                    current_element["text"] = span["text"]
                current_element["y_end"] = max(current_element["y_end"], span["bbox"][3])

        # Flush final element
        if current_element["text"].strip():
            self._evaluate_element_role(current_element, body_font)
            elements.append(current_element)

        return elements

    def _evaluate_element_role(self, element: Dict[str, Any], body_font: float) -> None:
        """
        Determines if a text block is a heading and calculates its hierarchy level.
        """
        text = element["text"].strip()
        size = element["size"]
        font = element["font"].lower()
        
        # Simple structural cues: Bold fonts or fonts larger than body font
        is_bold = "bold" in font or "black" in font or "heavy" in font
        
        # Check if the title text matches numbered section prefixes (e.g., 1.1, 2.0, SECTION 1)
        numbered_prefix = bool(re.match(r"^(\d+\.)+\d*\s+", text) or re.match(r"^section\s+\d+", text, re.IGNORECASE))
        
        # Heading criteria
        if size > body_font + 1.0 or (size >= body_font and is_bold) or numbered_prefix:
            element["is_heading"] = True
            
            # Map font size dynamically to heading levels (0-based)
            if size > body_font + 6.0:
                element["level"] = 0  # H1 / Chapter
            elif size > body_font + 3.0:
                element["level"] = 1  # H2 / Section
            elif size > body_font + 1.0:
                element["level"] = 2  # H3 / Subsection
            else:
                element["level"] = 3  # H4 / Minor section (Bold inline header)
        else:
            element["is_heading"] = False

    def _merge_tables_into_elements(self, text_elements: List[Dict[str, Any]], tables: List[Dict[str, Any]], page_num: int) -> List[Dict[str, Any]]:
        """
        Combines text elements and table elements on a page in their physical top-to-bottom reading order.
        """
        all_elements = text_elements + tables
        # Sort by vertical starting position
        all_elements.sort(key=lambda x: x.get("y_start") if x["type"] == "text" else x.get("top"))
        return all_elements

    def _reconstruct_hierarchy(self, elements: List[Dict[str, Any]], version_number: int) -> List[Dict[str, Any]]:
        """
        Reconstructs the hierarchical document tree from a list of elements.
        Uses a stack to track parent nodes and nested levels.
        """
        nodes = []
        
        # Create a default root node to hold intro text before any heading
        root_uuid = str(uuid.uuid4())
        root_node = {
            "id": root_uuid,
            "node_uuid": root_uuid,
            "title": "Document Summary",
            "level": 0,
            "body": "",
            "page_number": 1,
            "parent_id": None,
            "children": [],
            "content_hash": "",
            "document_version": version_number,
            "created_at": datetime.now()
        }
        
        # We start with the root node in our active heading stack
        stack = [root_node]
        
        for el in elements:
            if el.get("type") == "table":
                # Tables are appended to the body of the current active heading
                if stack:
                    parent = stack[-1]
                    if parent["body"]:
                        parent["body"] += "\n\n" + el["body"]
                    else:
                        parent["body"] = el["body"]
                continue

            text = el["text"].strip()
            if not text:
                continue

            if el["is_heading"]:
                # Create a new heading node
                node_id = str(uuid.uuid4())
                new_node = {
                    "id": node_id,
                    "node_uuid": node_id,  # Initially node_uuid matches the ID for v1
                    "title": text,
                    "level": el["level"] + 1,  # Shift down by 1 because 0 is root
                    "body": "",
                    "page_number": el["page_number"],
                    "parent_id": None,
                    "children": [],
                    "content_hash": "",
                    "document_version": version_number,
                    "created_at": datetime.now()
                }

                # Find the parent heading level in our stack
                while len(stack) > 1 and stack[-1]["level"] >= new_node["level"]:
                    stack.pop()

                if stack:
                    new_node["parent_id"] = stack[-1]["id"]
                    stack[-1]["children"].append(new_node["id"])

                nodes.append(new_node)
                stack.append(new_node)
            else:
                # It is a paragraph. Append to the current active heading
                if stack:
                    parent = stack[-1]
                    if parent["body"]:
                        parent["body"] += "\n\n" + text
                    else:
                        parent["body"] = text

        # Add the root node if it accumulated any body text before other headings
        root_node["content_hash"] = generate_node_hash(root_node["title"], root_node["body"])
        if root_node["body"].strip() or root_node["children"]:
            # Insert root node at the beginning of the document
            nodes.insert(0, root_node)
        else:
            # If root is empty and has no children, we can discard it.
            # But let's fix parent_id references for nodes that have parent_id == root_node["id"]
            for node in nodes:
                if node["parent_id"] == root_node["id"]:
                    node["parent_id"] = None

        # Compute content hashes for all other generated nodes
        for node in nodes:
            if node["id"] != root_node["id"]:
                node["content_hash"] = generate_node_hash(node["title"], node["body"])

        return nodes
