import logging
from typing import List, Dict, Any, Tuple
from rapidfuzz import fuzz
from app.utils.helpers import generate_node_hash

logger = logging.getLogger("app.services.versioning")


class VersioningService:
    def __init__(self, similarity_threshold: float = 60.0):
        self.similarity_threshold = similarity_threshold

    def align_versions(
        self, v1_nodes: List[Dict[str, Any]], v2_nodes: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
        """
        Aligns Version 2 nodes against Version 1 nodes.
        Returns:
        1. The updated v2_nodes list where matching nodes inherit the 'node_uuid' from v1_nodes.
        2. A mapping dict of: {v2_node_id: comparison_status}
           where status is: "Unchanged", "Modified", "New", "Deleted"
        """
        logger.info(f"Aligning {len(v2_nodes)} v2 nodes against {len(v1_nodes)} v1 nodes...")
        
        # 1. Build helper paths for disambiguation
        v1_by_id = {n["id"]: n for n in v1_nodes}
        v2_by_id = {n["id"]: n for n in v2_nodes}
        
        v1_paths = {n["id"]: self._build_path_string(n, v1_by_id) for n in v1_nodes}
        v2_paths = {n["id"]: self._build_path_string(n, v2_by_id) for n in v2_nodes}

        # Tracks matches: {v2_node_id: v1_node_id} and vice versa
        v2_to_v1_matches: Dict[str, str] = {}
        v1_to_v2_matches: Dict[str, str] = {}

        # Step A: Match identical paths first (highly likely to be the same node structural position)
        v1_path_to_id = {path: node_id for node_id, path in v1_paths.items()}
        for v2_id, v2_path in v2_paths.items():
            if v2_path in v1_path_to_id:
                v1_id = v1_path_to_id[v2_path]
                # Ensure it hasn't been matched yet (should be unique by path)
                if v1_id not in v1_to_v2_matches:
                    v2_to_v1_matches[v2_id] = v1_id
                    v1_to_v2_matches[v1_id] = v2_id

        # Step B: For remaining unmatched v2 nodes, perform fuzzy matching against unmatched v1 nodes
        unmatched_v2 = [nid for nid in v2_by_id.keys() if nid not in v2_to_v1_matches]
        unmatched_v1 = [nid for nid in v1_by_id.keys() if nid not in v1_to_v2_matches]

        for v2_id in unmatched_v2:
            v2_node = v2_by_id[v2_id]
            best_v1_id = None
            best_score = 0.0

            for v1_id in unmatched_v1:
                v1_node = v1_by_id[v1_id]
                score = self._compute_similarity_score(v2_node, v1_node)
                
                if score > best_score:
                    best_score = score
                    best_v1_id = v1_id

            if best_v1_id and best_score >= self.similarity_threshold:
                v2_to_v1_matches[v2_id] = best_v1_id
                v1_to_v2_matches[best_v1_id] = v2_id
                # Remove matched v1 from list so it doesn't double-match
                unmatched_v1.remove(best_v1_id)

        # Step C: Assign UUIDs and determine statuses
        node_statuses: Dict[str, str] = {}
        
        # Process Version 2 nodes (Unchanged, Modified, New)
        for v2_node in v2_nodes:
            v2_id = v2_node["id"]
            if v2_id in v2_to_v1_matches:
                v1_id = v2_to_v1_matches[v2_id]
                v1_node = v1_by_id[v1_id]
                
                # Inherit the node_uuid to maintain historical continuity
                v2_node["node_uuid"] = v1_node["node_uuid"]
                
                # Compare content hashes to determine if modified
                if v2_node["content_hash"] == v1_node["content_hash"]:
                    node_statuses[v2_id] = "Unchanged"
                else:
                    node_statuses[v2_id] = "Modified"
            else:
                # No match found: Node is brand new. Keep its auto-generated node_uuid
                node_statuses[v2_id] = "New"

        # Find deleted nodes (V1 nodes not matched in V2)
        deleted_nodes = []
        for v1_node in v1_nodes:
            v1_id = v1_node["id"]
            if v1_id not in v1_to_v2_matches:
                node_statuses[v1_id] = "Deleted"

        logger.info(
            f"Alignment complete. Results: "
            f"Unchanged={list(node_statuses.values()).count('Unchanged')}, "
            f"Modified={list(node_statuses.values()).count('Modified')}, "
            f"New={list(node_statuses.values()).count('New')}, "
            f"Deleted={list(node_statuses.values()).count('Deleted')}"
        )
        return v2_nodes, node_statuses

    def _build_path_string(self, node: Dict[str, Any], nodes_by_id: Dict[str, Dict[str, Any]]) -> str:
        """
        Recursively builds a path string based on headings (e.g. "/Document/Section 1/Subsection A").
        Helps disambiguate duplicate titles located in different sections.
        """
        path_segments = [node["title"]]
        parent_id = node.get("parent_id")
        
        # Traverse upwards to prevent infinite loops limit to depth 15
        depth = 0
        while parent_id and parent_id in nodes_by_id and depth < 15:
            parent_node = nodes_by_id[parent_id]
            path_segments.insert(0, parent_node["title"])
            parent_id = parent_node.get("parent_id")
            depth += 1
            
        return "/" + "/".join(path_segments)

    def _compute_similarity_score(self, n2: Dict[str, Any], n1: Dict[str, Any]) -> float:
        """
        Computes a composite similarity score between two nodes using token-based fuzzy matching.
        Returns a value between 0.0 and 100.0.
        """
        # Title similarity (40% weight)
        title_score = fuzz.token_sort_ratio(n2["title"], n1["title"])
        
        # Body similarity (60% weight)
        body_score = fuzz.token_set_ratio(n2["body"], n1["body"])
        
        # Return composite score
        return (title_score * 0.4) + (body_score * 0.6)
