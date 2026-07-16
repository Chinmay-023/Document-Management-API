import pytest
import io
import fitz  # PyMuPDF


def create_dummy_pdf_bytes(headings_and_body: list) -> bytes:
    """
    Helper function to generate a valid PDF byte stream in-memory.
    """
    doc = fitz.open()
    page = doc.new_page()
    
    y = 50
    for idx, (title, body) in enumerate(headings_and_body):
        # Insert Heading (Bold, larger font)
        page.insert_text((50, y), title, fontsize=14, fontname="hebo")
        y += 20
        # Insert Body text (Normal font)
        page.insert_text((50, y), body, fontsize=10, fontname="helv")
        y += 40
        
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_full_qa_system_workflow(client):
    """
    Integration test validating the complete workflow sequence across the REST endpoints.
    """
    # -------------------------------------------------------------
    # STEP 1: Upload Version 1 PDF
    # -------------------------------------------------------------
    v1_content = [
        ("1. Safety Protocols", "Do not operate in wet environments."),
        ("2. Inflation Controls", "Apply pressure up to 150 mmHg max.")
    ]
    pdf_v1_bytes = create_dummy_pdf_bytes(v1_content)
    
    upload_res = client.post(
        "/documents/upload",
        data={"name": "CardioTrack CT-200"},
        files={"file": ("manual_v1.pdf", pdf_v1_bytes, "application/pdf")}
    )
    
    assert upload_res.status_code == 201
    v1_data = upload_res.json()
    assert v1_data["version_number"] == 1
    version_1_id = v1_data["id"]
    document_id = v1_data["document_id"]

    # -------------------------------------------------------------
    # STEP 2: Browse document tree
    # -------------------------------------------------------------
    tree_res = client.get(f"/documents/tree/?version_id={version_1_id}")
    assert tree_res.status_code == 200
    tree_data = tree_res.json()
    
    # We should have the Root Summary node, and two parsed headings
    assert len(tree_data) >= 1
    
    # Find the node ID of "2. Inflation Controls"
    # Note: Depending on where text lies, the headings are children of Root Summary or roots themselves
    def find_node_by_title(nodes, search_title):
        for n in nodes:
            if search_title in n["title"]:
                return n
            if "children" in n and n["children"]:
                found = find_node_by_title(n["children"], search_title)
                if found:
                    return found
        return None

    inflation_node = find_node_by_title(tree_data, "Inflation Controls")
    assert inflation_node is not None
    inflation_node_id = inflation_node["id"]

    # -------------------------------------------------------------
    # STEP 3: Perform Fuzzy/Keyword Search
    # -------------------------------------------------------------
    search_res = client.get(f"/documents/search/?version_id={version_1_id}&query=inflation")
    assert search_res.status_code == 200
    search_data = search_res.json()
    assert len(search_data) > 0
    assert "Inflation" in search_data[0]["title"]

    # -------------------------------------------------------------
    # STEP 4: Create Selection
    # -------------------------------------------------------------
    selection_res = client.post(
        "/selection",
        json={
            "name": "Inflation Checks Pin",
            "document_version_id": version_1_id,
            "node_ids": [inflation_node_id]
        }
    )
    assert selection_res.status_code == 201
    selection_data = selection_res.json()
    selection_id = selection_data["id"]
    selection_hash = selection_data["selection_hash"]

    # -------------------------------------------------------------
    # STEP 5: Generate QA test cases
    # -------------------------------------------------------------
    gen_res = client.post(
        "/generate",
        json={
            "selection_id": selection_id,
            "llm_provider": "mock"
        }
    )
    assert gen_res.status_code == 201
    gen_data = gen_res.json()
    assert gen_data["status"] == "SUCCESS"
    generation_id = gen_data["id"]

    # -------------------------------------------------------------
    # STEP 6: Retrieve generated test cases
    # -------------------------------------------------------------
    retrieve_res = client.get(f"/generation/{generation_id}")
    assert retrieve_res.status_code == 200
    retrieve_data = retrieve_res.json()
    assert retrieve_data["status"] == "SUCCESS"
    assert len(retrieve_data["test_cases"]) == 3
    assert retrieve_data["test_cases"][0]["test_id"] == "TC-001"

    # -------------------------------------------------------------
    # STEP 7: Upload Version 2 PDF (with modified content)
    # -------------------------------------------------------------
    # Change "2. Inflation Controls" pressure to 180 mmHg
    v2_content = [
        ("1. Safety Protocols", "Do not operate in wet environments."),
        ("2. Inflation Controls", "Apply pressure up to 180 mmHg max.") # modified
    ]
    pdf_v2_bytes = create_dummy_pdf_bytes(v2_content)
    
    version_res = client.post(
        "/documents/version",
        data={"document_id": document_id},
        files={"file": ("manual_v2.pdf", pdf_v2_bytes, "application/pdf")}
    )
    assert version_res.status_code == 201
    v2_data = version_res.json()
    assert v2_data["version_number"] == 2
    version_2_id = v2_data["id"]

    # -------------------------------------------------------------
    # STEP 8: Browse Version 2 Tree & find modified node
    # -------------------------------------------------------------
    tree_res_v2 = client.get(f"/documents/tree/?version_id={version_2_id}")
    assert tree_res_v2.status_code == 200
    tree_data_v2 = tree_res_v2.json()
    
    inflation_node_v2 = find_node_by_title(tree_data_v2, "Inflation Controls")
    assert inflation_node_v2 is not None
    inflation_node_v2_id = inflation_node_v2["id"]

    # -------------------------------------------------------------
    # STEP 9: Check Node Diff
    # -------------------------------------------------------------
    diff_res = client.get(f"/diff/{inflation_node_v2_id}")
    assert diff_res.status_code == 200
    diff_data = diff_res.json()
    assert diff_data["similarity_score"] < 1.0
    assert "180 mmHg" in diff_data["added_text"]
    assert "150 mmHg" in diff_data["removed_text"]

    # -------------------------------------------------------------
    # STEP 10: Check Staleness
    # -------------------------------------------------------------
    staleness_res = client.get(f"/staleness/{generation_id}")
    assert staleness_res.status_code == 200
    staleness_data = staleness_res.json()
    
    # Since we uploaded v2 and modified the selected node, status should be Outdated
    assert staleness_data["status"] == "Outdated"
    assert staleness_data["new_version_available"] is True
    assert inflation_node_id in staleness_data["modified_node_ids"]
