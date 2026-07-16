# Technical Approach: AI-Powered QA Test Case Generation System

This document outlines the architectural rationale, engineering design decisions, hashing model, version matching heuristics, and trade-offs made during the development of this backend system.

---

## 1. Clean Architecture Design

We adopted **Clean Architecture** to maintain a strict separation of concerns, decoupling our core business logic from database systems, input web frameworks, and third-party APIs:

- **Entities / Models (`app/models/`)**: Relational database schemas mapping core objects (`Document`, `DocumentVersion`, `DocumentNode`, `Selection`, `SelectionNode`, `Generation`, `GenerationNode`).
- **Repositories (`app/repositories/`)**: Abstracted query operations, segregating transactional queries from HTTP request routers.
- **Services (`app/services/`)**: Business domain components (PDF parser, fuzzy aligner, diff engine, LLM interface).
- **APIs / Controllers (`app/api/`)**: Handle HTTP requests, manage multipart inputs, catch exceptions, and format Pydantic serialization payloads.

### Multi-Database Hybrid Storage Pattern
We coupled **SQLite** (relational database engine) and **MongoDB** (unstructured document store) in a hybrid model:
1. **SQLite (via SQLAlchemy)** manages configuration state, entity-relationship integrity, audit trails, and versioning links.
2. **MongoDB (via Motor)** stores heavy, nested JSON payloads (like parsed document hierarchy trees and raw LLM-generated test case documents). This scales retrieval times and avoids inflating SQLite storage size.

---

## 2. PDF Parser Design

### Why PDF Parsing directly was chosen
Parsing technical PDFs directly—as opposed to converting them to markdown or plain text beforehand—is crucial in regulated medical environments:
- **No Intermediate Losses**: Standard text dumps garble tables and columns. By mapping text segments directly in PyMuPDF, we can isolate coordinate zones.
- **Table Isolation**: Using `pdfplumber`, we identify table coordinates (bounding boxes). We mask those regions from our main flow, parse cells separately, and inject formatted Markdown tables in place. This avoids scrambling numerical rows with nearby body lines.
- **Font & Indentation Mapping**: We analyze font sizes and weights page by page. Top-level headers are isolated by mapping relative size thresholds against the most common font size (body text), reconstructing hierarchy trees cleanly.

---

## 3. Content Hashing & Staleness Model

### Content Hashing
We generate a deterministic SHA256 hex string for each node:
`content_hash = SHA256("t:" + normalized_title + "|b:" + normalized_body)`
Text normalization includes stripping trailing whitespace, converting characters to lowercase, and collapsing multiple internal spaces or newlines into a single space.

### Staleness Heuristics
When a test case generation is initiated, the system stores the `selection_hash` and the specific node hashes. During retrieval:
- **Fresh**: Pinned nodes exist in the database, and their hashes match the current active version exactly.
- **Possibly Stale**: Pinned node hashes match, but a newer version of the main document has been uploaded. This alerts the QA team that surrounding context might have altered requirement scopes.
- **Outdated**: One or more selected nodes have been modified or deleted entirely in the latest version. The response lists the specific node IDs that triggered the warning, allowing users to pin target revisions.

---

## 4. Matching & Diff Logic

### Node Alignment Algorithm
When Version 2 of a PDF is uploaded, we must match its nodes against Version 1:
1. **Exact Path Matching**: We construct an absolute hierarchy path for every node (e.g., `/Overview/Warnings/Electrical Safety`). If paths are identical, nodes are aligned.
2. **Fuzzy Scoring**: For unmatched nodes, we compute a composite similarity index:
   `Score = (fuzz.token_sort_ratio(v2.title, v1.title) * 0.4) + (fuzz.token_set_ratio(v2.body, v1.body) * 0.6)`
   Nodes exceeding a `60%` threshold are aligned. Matching nodes in V2 inherit the `node_uuid` of their V1 parent, maintaining historical continuity.
3. **Diff Report**: For modified nodes, we run `difflib.ndiff` line-by-line to isolate additions (`+`) and deletions (`-`), supplying a summary string of change metrics.

---

## 5. Decision Log

### Q1: Where silent failures happen
- **MongoDB Disconnection**: If MongoDB fails during startup or execution, the system logs a warning instead of crashing. Relational SQLite calls function normally, and only rich JSON-heavy operations (e.g. tree retrieval details and test case list lookups) raise structured HTTP warnings.
- **Fuzzy Alignment Misses**: If a section is heavily rewritten, the fuzzy matching threshold may fail to align it. The node silently falls back to being classified as **New**, and the old node is marked as **Deleted**.

### Q2: Where simplicity was preferred
- **Mock LLM Provider**: To facilitate robust offline verification and prevent flaky API network errors in CI pipelines, we implemented a mock provider that yields high-fidelity blood pressure monitor test cases directly.
- **difflib vs AST analysis**: Line-by-line text comparison was favored over AST or semantic structure diffing to keep diff outputs readable for human QA engineers.

### Q3: Known unsupported inputs
- **Embedded Image Diagrams**: The parser extracts page text and tables but ignores vector images and scanned diagram flows.
- **Nested Column Scramble**: Complex technical manuals with multi-column sidebars may experience text flow lines interweaving if columns do not align to uniform page boundaries.
