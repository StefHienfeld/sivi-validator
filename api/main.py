"""
FastAPI application for SIVI AFD XML Validator web interface.

Version 2.0 - Gap Analysis Implementation

Engines:
    0. XSD Validatie (structuur, hierarchie)
    1. Schema Validatie (labels, codes, decimale precisie)
    2. Business Rules (premies, datums, BSN, IBAN, branche-dekking)
    3. LLM Semantische Analyse (AI-powered)
    4. XPath Verbandscontroles (relatie controles)
    5. Encoding & Data Quality (UTF-8, BOM, placeholders)
    F. Certificering (verzendklaar garantie)

Usage:
    uvicorn api.main:app --reload --port 8000

Access at http://localhost:8000
"""

import os
import sys
from pathlib import Path
from typing import Optional, Set

from dotenv import load_dotenv
from fastapi import FastAPI, File, Query, UploadFile, HTTPException, Header, BackgroundTasks

# Load .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# Get API key from environment
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config, set_config
from engines.base import BatchData, Finding
from engines.engine0_xsd import XSDValidationEngine
from engines.engine1_schema import SchemaValidationEngine
from engines.engine2_rules import BusinessRulesEngine
from engines.engine3_llm import LLMSemanticEngine
from engines.engine_xpath import XPathBusinessRulesEngine
from engines.engine_encoding import EncodingValidationEngine
from engines.engine_final import FinalValidationEngine, SIVICertificationIntegration
from parser.xml_parser import XMLParser
from parser.version_manager import detect_xml_version
from report.json_reporter import JSONReporter

# Chatbot imports
from chatbot.models.schemas import (
    ChatRequest,
    ChatResponse,
    FindingContext,
    KnowledgeStatus,
    SuggestRequest,
    SuggestResponse,
)
from chatbot.chat.engine import ChatEngine

# Initialize FastAPI app
app = FastAPI(
    title="SIVI AFD Validator",
    description="Web interface for validating SIVI AFD XML files (v2.0 - Gap Analysis Implementation)",
    version="2.0.0",
)

# Configure CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize configuration
config = Config()
set_config(config)

# Frontend directory
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# Initialize chat engine (lazy loaded)
_chat_engine: Optional[ChatEngine] = None


def get_chat_engine() -> ChatEngine:
    """Get or create the chat engine instance."""
    global _chat_engine
    if _chat_engine is None:
        sivi_dir = Path(config.sivi_dir)
        data_dir = Path(__file__).parent.parent / "data"
        _chat_engine = ChatEngine(
            sivi_dir=sivi_dir,
            data_dir=data_dir,
            api_key=ANTHROPIC_API_KEY,
        )
    return _chat_engine


def parse_engines(engines_str: Optional[str]) -> Set[int]:
    """Parse engines string like '0,1,2,4,5' into set of integers."""
    if not engines_str:
        return {0, 1, 2, 4, 5}  # Default: all except LLM (3)

    engines = set()
    for part in engines_str.split(","):
        try:
            engine_num = int(part.strip())
            if engine_num in (0, 1, 2, 3, 4, 5):
                engines.add(engine_num)
        except ValueError:
            pass

    return engines if engines else {0, 1, 2, 4, 5}


def validate_batch(
    batch: BatchData,
    engines: Set[int],
    api_key: Optional[str] = None,
    certify: bool = False,
) -> list[Finding]:
    """Run validation engines on a batch."""
    findings = []

    # Engine 0: XSD validation
    if 0 in engines:
        engine0 = XSDValidationEngine(config)
        findings.extend(engine0.validate(batch))

    # Engine 5: Encoding & data quality (run early to catch encoding issues)
    if 5 in engines:
        engine5 = EncodingValidationEngine(config)
        findings.extend(engine5.validate(batch))

    # Engine 1: Schema validation (includes decimal precision)
    if 1 in engines:
        engine1 = SchemaValidationEngine(config)
        findings.extend(engine1.validate(batch))

    # Engine 2: Business rules (extended with branch-coverage, etc.)
    if 2 in engines:
        engine2 = BusinessRulesEngine(config)
        findings.extend(engine2.validate(batch))

    # Engine 4: XPath verbandscontroles
    if 4 in engines:
        engine4 = XPathBusinessRulesEngine(config)
        findings.extend(engine4.validate(batch))

    # Engine 3: LLM semantic analysis
    if 3 in engines and api_key:
        engine3 = LLMSemanticEngine(config, api_key=api_key)
        findings.extend(engine3.validate(batch))

    # Final certification
    if certify and config.enable_final_certification:
        final_engine = FinalValidationEngine(config)
        final_findings, certificate = final_engine.validate_and_certify(batch, findings)
        findings.extend(final_findings)

    return findings


@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.get("/styles.css")
async def serve_styles():
    """Serve the CSS file."""
    css_path = FRONTEND_DIR / "styles.css"
    if not css_path.exists():
        raise HTTPException(status_code=404, detail="CSS not found")
    return FileResponse(css_path, media_type="text/css")


@app.get("/app.js")
async def serve_javascript():
    """Serve the JavaScript file."""
    js_path = FRONTEND_DIR / "app.js"
    if not js_path.exists():
        raise HTTPException(status_code=404, detail="JavaScript not found")
    return FileResponse(js_path, media_type="application/javascript")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "validator": "sivi-validator",
        "version": "2.0.0",
        "engines": {
            0: "XSD Validatie",
            1: "Schema Validatie",
            2: "Business Rules",
            3: "LLM Semantic",
            4: "XPath Verbandscontroles",
            5: "Encoding & Data Quality",
        },
    }


@app.get("/api/config")
async def get_config():
    """Get configuration info for the frontend."""
    return {
        "has_api_key": bool(ANTHROPIC_API_KEY and ANTHROPIC_API_KEY.startswith("sk-")),
        "version": "2.0.0",
        "engines_available": [0, 1, 2, 3, 4, 5],
        "default_engines": [0, 1, 2, 4, 5],
    }


@app.get("/api/sivi-certification")
async def get_sivi_certification_info():
    """Get information about official SIVI certification."""
    integration = SIVICertificationIntegration(config)
    return integration.get_certification_info()


@app.post("/api/validate")
async def validate_xml(
    file: UploadFile = File(...),
    engines: Optional[str] = Query(
        default="0,1,2,4,5",
        description="Comma-separated engine numbers: 0=XSD, 1=Schema, 2=Rules, 3=LLM, 4=XPath, 5=Encoding"
    ),
    certify: bool = Query(default=False, description="Enable final certification"),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Validate an uploaded XML file.

    - **file**: The XML file to validate
    - **engines**: Comma-separated list of engines:
        - 0: XSD Validatie (structuur, hierarchie)
        - 1: Schema Validatie (labels, codes, decimale precisie)
        - 2: Business Rules (premies, datums, BSN, IBAN, branche)
        - 3: LLM Semantic (AI-powered, requires API key)
        - 4: XPath Verbandscontroles (relatie controles)
        - 5: Encoding & Data Quality (UTF-8, BOM, placeholders)
    - **certify**: Enable final certification check
    - **X-API-Key**: Anthropic API key for Engine 3 (LLM) - optional header
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not file.filename.lower().endswith(".xml"):
        raise HTTPException(status_code=400, detail="File must be an XML file")

    # Read file content
    try:
        content = await file.read()
        xml_string = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. File must be UTF-8 encoded.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")

    # Parse engines
    engine_set = parse_engines(engines)

    # Use API key from header, or fall back to .env
    api_key = x_api_key or ANTHROPIC_API_KEY

    # Check if LLM engine is requested but no API key provided
    if 3 in engine_set and not api_key:
        engine_set.discard(3)

    # Parse XML
    try:
        parser = XMLParser()
        batch = parser.parse_string(xml_string)
        batch.source_file = file.filename
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing XML: {str(e)}")

    # Validate
    try:
        findings = validate_batch(batch, engine_set, api_key, certify=certify)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")

    # Generate JSON report using existing reporter
    reporter = JSONReporter()
    report = reporter._build_report(findings, file.filename, {
        "engines_requested": list(engine_set),
        "contracts_parsed": len(batch.contracts),
    })

    return JSONResponse(content=report)


# =============================================================================
# Chat API Endpoints
# =============================================================================


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Send a chat message and get a response.

    - **message**: The user's question
    - **conversation_id**: Optional conversation ID for context
    - **finding_context**: Optional validation finding for context
    - **validation_file**: Optional name of the validated file
    """
    api_key = x_api_key or ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key required for chat functionality. Provide via X-API-Key header or ANTHROPIC_API_KEY env var.",
        )

    try:
        engine = get_chat_engine()
        engine.api_key = api_key
        response = await engine.chat(request)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.post("/api/chat/suggest", response_model=SuggestResponse)
async def suggest_questions(
    request: SuggestRequest,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Get suggested questions for a validation finding.

    - **finding**: The finding to get suggestions for
    """
    api_key = x_api_key or ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key required for suggestions.",
        )

    try:
        engine = get_chat_engine()
        engine.api_key = api_key
        response = await engine.suggest_questions(request.finding)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Suggestion error: {str(e)}")


@app.get("/api/knowledge/status", response_model=KnowledgeStatus)
async def knowledge_status():
    """Get the status of the knowledge base."""
    try:
        engine = get_chat_engine()
        return engine.get_knowledge_status()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status error: {str(e)}")


@app.post("/api/knowledge/rebuild")
async def rebuild_knowledge(
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
):
    """
    Rebuild the knowledge base from all sources.

    This operation runs in the background and may take a few minutes.
    """
    api_key = x_api_key or ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="API key required for admin operations.",
        )

    async def rebuild_task():
        engine = get_chat_engine()
        await engine.rebuild_knowledge_base()

    background_tasks.add_task(rebuild_task)

    return {
        "status": "started",
        "message": "Knowledge base rebuild started. Check /api/knowledge/status for progress.",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
