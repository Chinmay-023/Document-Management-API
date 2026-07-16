import pytest
from app.services.versioning import VersioningService
from app.services.diff import DiffService
from app.utils.helpers import generate_node_hash


def test_node_alignment_classification():
    """
    Verifies that the VersioningService aligns v2 nodes to v1 nodes and
    properly classifies unchanged, modified, deleted, and new nodes.
    """
    v1_nodes = [
        {
            "id": "v1-node-1",
            "node_uuid": "uuid-1",
            "title": "1. Safety Rules",
            "level": 1,
            "body": "Do not swallow batteries.",
            "page_number": 1,
            "parent_id": None,
            "content_hash": generate_node_hash("1. Safety Rules", "Do not swallow batteries.")
        },
        {
            "id": "v1-node-2",
            "node_uuid": "uuid-2",
            "title": "2. Measurement Settings",
            "level": 1,
            "body": "Inflate the cuff to 150 mmHg.",
            "page_number": 2,
            "parent_id": None,
            "content_hash": generate_node_hash("2. Measurement Settings", "Inflate the cuff to 150 mmHg.")
        }
    ]

    # V2 changes:
    # 1. "1. Safety Rules" is unchanged.
    # 2. "2. Measurement Settings" is modified (pressure updated).
    # 3. New section "3. Maintenance Guide" is added.
    # 4. A previously deleted node (not included in v2).
    v2_nodes = [
        {
            "id": "v2-node-1",
            "node_uuid": "v2-node-1-newuuid",  # Initial arbitrary UUID
            "title": "1. Safety Rules",
            "level": 1,
            "body": "Do not swallow batteries.",
            "page_number": 1,
            "parent_id": None,
            "content_hash": generate_node_hash("1. Safety Rules", "Do not swallow batteries.")
        },
        {
            "id": "v2-node-2",
            "node_uuid": "v2-node-2-newuuid",
            "title": "2. Measurement Settings",
            "level": 1,
            "body": "Inflate the cuff to 180 mmHg.",  # Content changed
            "page_number": 2,
            "parent_id": None,
            "content_hash": generate_node_hash("2. Measurement Settings", "Inflate the cuff to 180 mmHg.")
        },
        {
            "id": "v2-node-3",
            "node_uuid": "v2-node-3-newuuid",
            "title": "3. Maintenance Guide",
            "level": 1,
            "body": "Clean with a soft damp cloth.",
            "page_number": 3,
            "parent_id": None,
            "content_hash": generate_node_hash("3. Maintenance Guide", "Clean with a soft damp cloth.")
        }
    ]

    aligner = VersioningService()
    aligned_v2, statuses = aligner.align_versions(v1_nodes, v2_nodes)

    # Verify that v2-node-1 aligned and inherited UUID-1
    node1 = next(n for n in aligned_v2 if n["id"] == "v2-node-1")
    assert node1["node_uuid"] == "uuid-1"
    assert statuses["v2-node-1"] == "Unchanged"

    # Verify that v2-node-2 aligned and inherited UUID-2, but status is Modified
    node2 = next(n for n in aligned_v2 if n["id"] == "v2-node-2")
    assert node2["node_uuid"] == "uuid-2"
    assert statuses["v2-node-2"] == "Modified"

    # Verify that v2-node-3 is classified as New and kept its UUID
    node3 = next(n for n in aligned_v2 if n["id"] == "v2-node-3")
    assert node3["node_uuid"] == "v2-node-3-newuuid"
    assert statuses["v2-node-3"] == "New"
    # Let's see: v1-node-1 is Unchanged, v1-node-2 is Modified.
    # What about deleted? Any v1 nodes NOT matched: in our mock, there is no unmatched v1 node. Let's add one to check.


def test_node_alignment_deletion():
    """
    Specifically tests categorization of deleted nodes.
    """
    v1_nodes = [
        {
            "id": "v1-node-deleted",
            "node_uuid": "uuid-del",
            "title": "Old Outdated Appendix",
            "level": 1,
            "body": "This body is no longer needed.",
            "page_number": 4,
            "parent_id": None,
            "content_hash": "hash-del"
        }
    ]
    v2_nodes = []

    aligner = VersioningService()
    _, statuses = aligner.align_versions(v1_nodes, v2_nodes)
    
    assert statuses["v1-node-deleted"] == "Deleted"


def test_diff_engine():
    """
    Tests text differentiation outputs, line comparisons, and similarity ratios.
    """
    old_title = "Safety Section"
    old_body = "Place the cuff on your upper arm.\nKeep arm still."
    
    new_title = "Safety Section"
    new_body = "Place the cuff on your upper left arm.\nKeep arm still."
    new_hash = "updated-hash-val"

    diff_svc = DiffService()
    report = diff_svc.compute_diff(old_title, old_body, new_title, new_body, new_hash)

    assert report["similarity_score"] > 0.0
    assert report["changed_hash"] == new_hash
    assert "Added 1 line" in report["diff_summary"]
    assert "Removed 1 line" in report["diff_summary"]
    assert "upper left arm" in report["added_text"]
    assert "upper arm" in report["removed_text"]
