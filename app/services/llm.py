import json
import logging
from typing import List, Dict, Any, Tuple, Optional
import httpx
from sqlalchemy.orm import Session
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.models.selection import Selection
from app.models.generation import Generation, GenerationNode
from app.schemas.generation import TestCase, PriorityEnum, RiskEnum
from app.repositories.document import DocumentNodeRepository
from app.repositories.generation import GenerationRepository, GenerationNodeRepository
import app.database.mongodb

logger = logging.getLogger("app.services.llm")

# Strict JSON Schema definition for LLM structured output
TEST_CASE_SCHEMA = {
    "type": "array",
    "description": "List of 3 to 5 QA test cases generated from the input document text.",
    "items": {
        "type": "object",
        "properties": {
            "test_id": {"type": "string", "description": "Unique test case identifier (e.g. TC-001)"},
            "title": {"type": "string", "description": "Short, clear title describing the test scenario"},
            "requirement_ref": {"type": "string", "description": "The header title or section number referenced from the text"},
            "preconditions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Preconditions required before starting test execution"
            },
            "steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Step-by-step instructions to execute the test case"
            },
            "expected_result": {"type": "string", "description": "The exact expected behavior confirming success"},
            "priority": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "risk": {"type": "string", "enum": ["CRITICAL", "MAJOR", "MINOR"]},
            "reason": {"type": "string", "description": "Reasoning for the selected priority/risk based on patient safety and device integrity"}
        },
        "required": ["test_id", "title", "requirement_ref", "preconditions", "steps", "expected_result", "priority", "risk", "reason"]
    }
}


class LLMService:
    def __init__(self, db: Session):
        self.db = db
        self.node_repo = DocumentNodeRepository(db)
        self.gen_repo = GenerationRepository(db)
        self.gen_node_repo = GenerationNodeRepository(db)

    async def generate_test_cases(
        self, selection_id: str, provider: Optional[str] = None, model: Optional[str] = None
    ) -> Tuple[Generation, List[TestCase]]:
        """
        Gathers selected requirements, formats an LLM prompt, queries the API with JSON enforcement,
        validates the schema with retries, and saves metadata in SQLite and JSON records in MongoDB.
        """
        # 1. Resolve LLM configuration options
        llm_provider = provider or settings.LLM_PROVIDER
        model_name = model or settings.LLM_MODEL
        
        logger.info(f"Initiating test case generation for Selection ID {selection_id} via {llm_provider} ({model_name})...")

        # 2. Retrieve Selection and Node contents
        selection = self.db.get(Selection, selection_id)
        if not selection:
            raise ValueError(f"Selection '{selection_id}' not found.")

        sel_nodes = selection.nodes
        if not sel_nodes:
            raise ValueError(f"No nodes found in selection '{selection_id}'.")

        # Fetch actual node content
        node_ids = [sn.node_id for sn in sel_nodes]
        nodes = self.node_repo.get_nodes_by_ids(node_ids)
        
        # Sort nodes by page and hierarchy path to preserve vertical document context
        nodes.sort(key=lambda n: (n.page_number, n.level, n.id))

        # Reconstruct requirements text block
        requirements_payload = ""
        for node in nodes:
            requirements_payload += f"--- SECTION: {node.title} (Page {node.page_number}) ---\n"
            requirements_payload += f"{node.body}\n\n"

        # 3. Formulate Prompt
        prompt = self._build_prompt(requirements_payload)

        # 4. Invoke LLM with Schema Validation and 1-Time Retry
        raw_response = ""
        parsed_cases = []
        validation_error = None

        try:
            raw_response = await self._call_llm_api(llm_provider, model_name, prompt)
            parsed_cases, validation_error = self._validate_and_parse_response(raw_response)
            
            if validation_error:
                logger.warning(f"First-attempt LLM response failed validation: {validation_error}. Retrying once...")
                retry_prompt = self._build_retry_prompt(requirements_payload, raw_response, validation_error)
                raw_response = await self._call_llm_api(llm_provider, model_name, retry_prompt)
                parsed_cases, validation_error = self._validate_and_parse_response(raw_response)
                
        except Exception as e:
            logger.error(f"Failed to communicate with LLM API: {e}")
            validation_error = str(e)

        # 5. Determine Database status and save
        status = "SUCCESS" if not validation_error else "FAILED"
        
        # Create SQL Generation row
        generation = Generation(
            selection_id=selection.id,
            selection_hash=selection.selection_hash,
            llm_provider=llm_provider,
            model_name=model_name,
            status=status,
            error_message=validation_error
        )
        self.gen_repo.create(generation)

        # Save consumed node mappings
        for node in nodes:
            gen_node = GenerationNode(
                generation_id=generation.id,
                node_id=node.id,
                content_hash=node.content_hash
            )
            self.gen_node_repo.create(gen_node)

        if status == "SUCCESS":
            # 6. Save final Test Cases list to MongoDB
            try:
                mongo_db = await app.database.mongodb.get_mongodb()
                if mongo_db is not None:
                    test_cases_payload = [tc.model_dump() for tc in parsed_cases]
                    await mongo_db.test_cases.insert_one({
                        "generation_id": generation.id,
                        "selection_id": selection_id,
                        "test_cases": test_cases_payload,
                        "provider": llm_provider,
                        "model": model_name
                    })
                    logger.info(f"Successfully saved {len(parsed_cases)} test cases to MongoDB.")
            except Exception as e:
                logger.error(f"Failed to store generated test cases in MongoDB: {e}")
        else:
            logger.error(f"Generation marked as FAILED. Reason: {validation_error}")
            if not parsed_cases and not validation_error:
                validation_error = "Zero test cases parsed."
                generation.error_message = validation_error
                self.db.add(generation)
                self.db.commit()

        return generation, parsed_cases

    def _build_prompt(self, requirements: str) -> str:
        """
        Creates the instructions for the AI model, enforcing medical device quality standards and structured output format.
        """
        return f"""You are a Senior Medical Device Quality Assurance Engineer.
Your task is to analyze technical requirements for a medical device and generate 3 to 5 highly detailed QA test cases.

Technical Context / Product Manual Excerpt:
\"\"\"
{requirements}
\"\"\"

Guidelines for Test Case Design:
1. Ensure coverage of safety-critical elements, error boundaries, user prompts, and device behaviors.
2. Formulate steps clearly, specifying expected values.
3. Assess Priority and Risk:
   - Priority must be HIGH, MEDIUM, or LOW.
   - Risk must be CRITICAL, MAJOR, or MINOR.
   - Explain the reasoning (safety, hazard mitigations, accuracy parameters) behind these ratings.

Output Requirements:
Return a STRICT JSON list of test objects. Do NOT wrap inside backticks (```json ... ```) or add any markdown formatting.
Verify that the output aligns exactly with the following JSON schema:
{json.dumps(TEST_CASE_SCHEMA, indent=2)}
"""

    def _build_retry_prompt(self, requirements: str, previous_output: str, error_msg: str) -> str:
        """
        Re-prompts the model on schema failure, feeding back the error message to enforce correction.
        """
        return f"""You are a Senior Medical Device Quality Assurance Engineer.
Your previous response failed JSON schema validation with the following error:
{error_msg}

Previous response:
\"\"\"
{previous_output}
\"\"\"

Please re-generate the 3 to 5 QA test cases from the technical requirements below. Correct the JSON syntax and schema issues, ensuring that it is a valid JSON array and contains all required keys. Do NOT include markdown blocks.

Technical Context:
\"\"\"
{requirements}
\"\"\"
"""

    async def _call_llm_api(self, provider: str, model: str, prompt: str) -> str:
        """
        Dispatches prompt requests to Gemini, OpenAI, or falls back to standard Mock data.
        """
        if provider == "mock":
            logger.info("Using mock LLM generator...")
            return self._generate_mock_response()

        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY environment variable is not set.")
            
            logger.info("Posting request to OpenAI completion endpoint...")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                )
                response.raise_for_status()
                res_data = response.json()
                content = res_data["choices"][0]["message"]["content"]
                return content

        if provider == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY environment variable is not set.")
            
            logger.info("Posting request to Gemini model endpoint...")
            # Use beta endpoint to enforce JSON schema structured outputs
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "responseMimeType": "application/json",
                            "responseSchema": TEST_CASE_SCHEMA,
                            "temperature": 0.1
                        }
                    }
                )
                response.raise_for_status()
                res_data = response.json()
                content = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return content

        raise ValueError(f"Unsupported LLM Provider: {provider}")

    def _validate_and_parse_response(self, response_text: str) -> Tuple[List[TestCase], Optional[str]]:
        """
        Parses the JSON output and verifies compliance with the structured TestCase schemas.
        """
        try:
            # Clean string in case the LLM returned markdown blocks despite prompt instruction
            cleaned_text = response_text.strip()
            if cleaned_text.startswith("```"):
                lines = cleaned_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1] == "```":
                    lines = lines[:-1]
                cleaned_text = "\n".join(lines).strip()

            raw_list = json.loads(cleaned_text)
            
            # If the LLM wraps the list in an envelope object (e.g. {"test_cases": [...]})
            if isinstance(raw_list, dict):
                for key in ["test_cases", "cases", "tests", "data"]:
                    if key in raw_list and isinstance(raw_list[key], list):
                        raw_list = raw_list[key]
                        break

            if not isinstance(raw_list, list):
                return [], "Response did not resolve into a JSON array list."

            test_cases = []
            for item in raw_list:
                # Let Pydantic validate and cast the individual test case
                tc = TestCase(**item)
                test_cases.append(tc)

            return test_cases, None

        except json.JSONDecodeError as jde:
            return [], f"Invalid JSON string: {jde}"
        except Exception as e:
            return [], f"Schema validation error: {str(e)}"

    def _generate_mock_response(self) -> str:
        """
        Returns a mock, valid medical-device-grade test case JSON string for local testing.
        """
        mock_cases = [
            {
                "test_id": "TC-001",
                "title": "Systolic Blood Pressure Range Limit Testing",
                "requirement_ref": "System Specifications",
                "preconditions": [
                    "CardioTrack CT-200 device is powered on.",
                    "Calibration simulator is connected to the cuff receptor port."
                ],
                "steps": [
                    "Configure simulator to generate a pressure corresponding to 220 mmHg.",
                    "Trigger measurement cycle on the device.",
                    "Verify display and log outputs."
                ],
                "expected_result": "The device accurately measures 220 mmHg +/- 3 mmHg and records values inside the non-volatile system log.",
                "priority": "HIGH",
                "risk": "MAJOR",
                "reason": "Accurate readings in high-systolic states are vital to alert patients of hypertensive crises."
            },
            {
                "test_id": "TC-002",
                "title": "Cuff Over-Pressure Safety Shutdown",
                "requirement_ref": "Safety Protocols",
                "preconditions": [
                    "Device is initialized in normal measurement mode.",
                    "Air pressure sensor is monitored."
                ],
                "steps": [
                    "Simulate restricted exhaust tube blockage during cuff inflation.",
                    "Force cuff air pressure to rise to 295 mmHg.",
                    "Monitor pneumatic valve state and motor power."
                ],
                "expected_result": "The pressure release valve opens immediately, power is cut to the pump, and Error Code 'E-02' (Overpressure) displays.",
                "priority": "HIGH",
                "risk": "CRITICAL",
                "reason": "Exceeding 290 mmHg without automated deflation poses serious vascular constriction and safety risks to patients."
            },
            {
                "test_id": "TC-003",
                "title": "Irregular Heartbeat (IHB) Visual Warning Indicator",
                "requirement_ref": "LCD Display Interface",
                "preconditions": [
                    "Cuff calibration simulator mimics heart arrhythmia intervals (pulse interval variation > 25%)."
                ],
                "steps": [
                    "Run standard inflation and measurement cycle.",
                    "Wait for calculation completion.",
                    "Inspect LCD indicators."
                ],
                "expected_result": "LCD screen displays final blood pressure numbers along with the flashing heart-symbol warning for irregular beats.",
                "priority": "MEDIUM",
                "risk": "MINOR",
                "reason": "Ensures cardiac indicator informs users of potential arrythmia without triggering severe false panic."
            }
        ]
        return json.dumps(mock_cases)
