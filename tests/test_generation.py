import pytest
from app.models.document import Document, DocumentVersion, DocumentNode
from app.models.selection import Selection, SelectionNode
from app.models.generation import Generation, GenerationNode
from app.services.selection import SelectionService
from app.services.llm import LLMService
from app.services.staleness import StalenessService
from app.schemas.generation import StalenessStatusEnum
from app.utils.helpers import generate_node_hash


@pytest.fixture
def sample_setup(db_session):
    """
    Sets up a simple document with version 1 in SQLite to run tests.
    """
    # Create Document
    doc = Document(name="CardioTrack CT-200")
    db_session.add(doc)
    db_session.commit()

    # Create Version 1
    v1 = DocumentVersion(
        document_id=doc.id,
        version_number=1,
        file_path="mock_v1.pdf"
    )
    db_session.add(v1)
    db_session.commit()

    # Create Nodes
    n1 = DocumentNode(
        node_uuid="uuid-node-a",
        document_version_id=v1.id,
        title="1. Safety Cues",
        level=1,
        body="Do not use on infants.",
        page_number=1,
        content_hash=generate_node_hash("1. Safety Cues", "Do not use on infants.")
    )
    n2 = DocumentNode(
        node_uuid="uuid-node-b",
        document_version_id=v1.id,
        title="2. Quick Start",
        level=1,
        body="Press power button.",
        page_number=2,
        content_hash=generate_node_hash("2. Quick Start", "Press power button.")
    )
    db_session.add_all([n1, n2])
    db_session.commit()

    return doc, v1, [n1, n2]


def test_selection_creation(db_session, sample_setup):
    """
    Tests saving a selection configuration, computing selection hashes, and mapping nodes.
    """
    doc, v1, nodes = sample_setup
    node_ids = [n.id for n in nodes]

    sel_svc = SelectionService(db_session)
    selection = sel_svc.create_selection(
        name="Critical Checks Selection",
        version_id=v1.id,
        node_ids=node_ids
    )

    assert selection.id is not None
    assert selection.name == "Critical Checks Selection"
    assert selection.document_version_id == v1.id
    assert len(selection.selection_hash) == 64
    assert len(selection.nodes) == 2


@pytest.mark.asyncio
async def test_llm_generation_mock(db_session, sample_setup):
    """
    Tests successful mock LLM test case generation and db commits.
    """
    doc, v1, nodes = sample_setup
    node_ids = [n.id for n in nodes]

    sel_svc = SelectionService(db_session)
    selection = sel_svc.create_selection(
        name="Mock Gen Selection",
        version_id=v1.id,
        node_ids=node_ids
    )

    llm_svc = LLMService(db_session)
    generation, cases = await llm_svc.generate_test_cases(
        selection_id=selection.id,
        provider="mock"
    )

    assert generation.id is not None
    assert generation.status == "SUCCESS"
    assert len(cases) == 3
    assert cases[0].test_id == "TC-001"
    assert len(generation.nodes) == 2


@pytest.mark.asyncio
async def test_llm_generation_schema_failure_retry(db_session, sample_setup, monkeypatch):
    """
    Tests LLM failure schema handler: triggers a retry, and records a failure on persistent error.
    """
    doc, v1, nodes = sample_setup
    
    sel_svc = SelectionService(db_session)
    selection = sel_svc.create_selection(
        name="Mock Failure Selection",
        version_id=v1.id,
        node_ids=[nodes[0].id]
    )

    # Mock call_llm_api to return invalid JSON on first and second try to trigger persistent failure
    call_count = 0
    async def mock_call(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return "Garbage response text that is not JSON"

    llm_svc = LLMService(db_session)
    monkeypatch.setattr(llm_svc, "_call_llm_api", mock_call)

    # Perform generation
    generation, cases = await llm_svc.generate_test_cases(
        selection_id=selection.id,
        provider="openai",  # Triggers the mock call
        model="gpt-4o"
    )

    # Verify that it retried once
    assert call_count == 2
    # Verify it failed gracefully and stored failure details
    assert generation.status == "FAILED"
    assert "Invalid JSON" in generation.error_message
    assert len(cases) == 0


def test_staleness_detection(db_session, sample_setup):
    """
    Tests evaluation of staleness states: Fresh, Possibly Stale, and Outdated.
    """
    doc, v1, nodes = sample_setup
    
    # Create Selection & Generation for Version 1
    sel_svc = SelectionService(db_session)
    selection = sel_svc.create_selection("Test Pinned", v1.id, [nodes[0].id])
    
    # Store dynamic generation
    gen = Generation(
        selection_id=selection.id,
        selection_hash=selection.selection_hash,
        llm_provider="mock",
        model_name="mock-model",
        status="SUCCESS"
    )
    db_session.add(gen)
    db_session.commit()
    
    # Connect generation nodes
    gen_node = GenerationNode(
        generation_id=gen.id,
        node_id=nodes[0].id,
        content_hash=nodes[0].content_hash
    )
    db_session.add(gen_node)
    db_session.commit()

    staleness_svc = StalenessService(db_session)

    # Scenario A: No newer version available -> Status should be FRESH
    report_a = staleness_svc.check_staleness(gen.id)
    assert report_a.status == StalenessStatusEnum.FRESH
    assert not report_a.new_version_available

    # Scenario B: Upload a new version (v2) where the selected node is UNCHANGED
    v2 = DocumentVersion(document_id=doc.id, version_number=2, file_path="mock_v2.pdf")
    db_session.add(v2)
    db_session.commit()

    # Create the node in Version 2 with IDENTICAL content (inheriting the same node_uuid)
    n1_v2 = DocumentNode(
        node_uuid=nodes[0].node_uuid, # Keep uuid link
        document_version_id=v2.id,
        title=nodes[0].title,
        level=nodes[0].level,
        body=nodes[0].body,
        page_number=nodes[0].page_number,
        content_hash=nodes[0].content_hash # Same hash
    )
    db_session.add(n1_v2)
    db_session.commit()

    # Running check: A new version exists, but our node is unchanged -> Status should be POSSIBLY_STALE
    report_b = staleness_svc.check_staleness(gen.id)
    assert report_b.status == StalenessStatusEnum.POSSIBLY_STALE
    assert report_b.new_version_available
    assert len(report_b.modified_node_ids) == 0

    # Scenario C: Modify the node in Version 2 (update body, change content hash)
    n1_v2.body = "Do not use on infants under 12 months."
    n1_v2.content_hash = generate_node_hash(n1_v2.title, n1_v2.body)
    db_session.add(n1_v2)
    db_session.commit()

    # Running check: Pinned node is modified -> Status should be OUTDATED
    report_c = staleness_svc.check_staleness(gen.id)
    assert report_c.status == StalenessStatusEnum.OUTDATED
    assert report_c.new_version_available
    assert nodes[0].id in report_c.modified_node_ids
