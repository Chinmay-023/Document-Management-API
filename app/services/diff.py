import difflib
import logging
from typing import Dict, Any
from rapidfuzz import fuzz

logger = logging.getLogger("app.services.diff")


class DiffService:
    def __init__(self):
        pass

    def compute_diff(self, old_title: str, old_body: str, new_title: str, new_body: str, new_hash: str) -> Dict[str, Any]:
        """
        Compares two nodes (old version vs new version) and generates structural diff content.
        """
        logger.info(f"Computing text diff for node change...")

        # 1. Compare body text using difflib
        old_lines = old_body.splitlines()
        new_lines = new_body.splitlines()
        
        diff = list(difflib.ndiff(old_lines, new_lines))
        
        added_lines = [line[2:] for line in diff if line.startswith("+ ")]
        removed_lines = [line[2:] for line in diff if line.startswith("- ")]
        
        added_text = "\n".join(added_lines)
        removed_text = "\n".join(removed_lines)

        # 2. Compute similarity score (ratio from 0.0 to 1.0)
        similarity = fuzz.ratio(old_body, new_body) / 100.0

        # 3. Create a descriptive summary of the changes
        title_changed = old_title != new_title
        summary_parts = []
        
        if title_changed:
            summary_parts.append(f"Heading changed from '{old_title}' to '{new_title}'.")
            
        added_count = len(added_lines)
        removed_count = len(removed_lines)
        
        if added_count > 0:
            summary_parts.append(f"Added {added_count} line(s) of text.")
        if removed_count > 0:
            summary_parts.append(f"Removed {removed_count} line(s) of text.")
            
        if not title_changed and added_count == 0 and removed_count == 0:
            # Inline whitespace or minor formatting change
            summary_parts.append("Minor formatting or spacing changes detected.")

        diff_summary = " ".join(summary_parts) if summary_parts else "No changes detected."

        return {
            "added_text": added_text,
            "removed_text": removed_text,
            "similarity_score": round(similarity, 3),
            "changed_hash": new_hash,
            "diff_summary": diff_summary
        }
