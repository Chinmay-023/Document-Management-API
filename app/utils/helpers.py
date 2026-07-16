import hashlib
import re
from typing import List


def normalize_text(text: str) -> str:
    """
    Standardizes input text by:
    1. Converting to lowercase
    2. Stripping leading/trailing whitespace
    3. Collapsing internal consecutive whitespace or newlines into a single space
    """
    if not text:
        return ""
    text = text.lower().strip()
    # Replace multiple whitespaces/newlines with a single space
    text = re.sub(r"\s+", " ", text)
    return text


def generate_node_hash(title: str, body: str) -> str:
    """
    Generates a deterministic SHA256 hex string from a normalized title and body.
    """
    norm_title = normalize_text(title)
    norm_body = normalize_text(body)
    
    # Delimit title and body to prevent boundary shift hash collisions
    combined = f"t:{norm_title}|b:{norm_body}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_selection_hash(node_hashes: List[str]) -> str:
    """
    Generates a deterministic SHA256 hash representing a set of selected node hashes.
    Sorts hashes first to ensure selection order does not affect the hash.
    """
    sorted_hashes = sorted(node_hashes)
    combined = ",".join(sorted_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
