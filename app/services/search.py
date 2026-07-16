import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from rapidfuzz import fuzz
from app.repositories.document import DocumentNodeRepository
from app.models.document import DocumentNode

logger = logging.getLogger("app.services.search")


class SearchService:
    def __init__(self, db: Session):
        self.node_repo = DocumentNodeRepository(db)

    def search_nodes(self, version_id: str, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Searches nodes within a document version by matching against title and body.
        Scores and ranks results using RapidFuzz token matching.
        """
        logger.info(f"Searching nodes in version {version_id} for query: '{query_text}'")
        
        # 1. Fetch all nodes for the document version
        nodes = self.node_repo.get_nodes_by_version(version_id)
        if not nodes:
            return []

        # 2. Score each node based on the query text
        scored_results = []
        for node in nodes:
            # Title matching (higher weight)
            title_score = fuzz.token_set_ratio(query_text, node.title)
            # Body matching (normal weight)
            body_score = fuzz.token_set_ratio(query_text, node.body)
            
            # Simple keyword frequency modifier
            keyword_bonus = 0.0
            keywords = query_text.lower().split()
            for kw in keywords:
                if len(kw) > 2:
                    if kw in node.title.lower():
                        keyword_bonus += 15.0
                    if kw in node.body.lower():
                        keyword_bonus += 5.0

            # Compute weighted score
            final_score = (title_score * 1.5) + body_score + keyword_bonus
            
            # Minimum threshold to filter irrelevant nodes
            if final_score > 25.0:
                scored_results.append({
                    "node": node,
                    "score": round(final_score, 2)
                })

        # 3. Sort by score in descending order
        scored_results.sort(key=lambda x: x["score"], reverse=True)

        # 4. Format outputs
        results = []
        for item in scored_results[:limit]:
            node: DocumentNode = item["node"]
            results.append({
                "id": node.id,
                "node_uuid": node.node_uuid,
                "title": node.title,
                "level": node.level,
                "body": node.body,
                "page_number": node.page_number,
                "parent_id": node.parent_id,
                "content_hash": node.content_hash,
                "score": item["score"]
            })

        return results
