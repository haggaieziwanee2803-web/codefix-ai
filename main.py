# ============================================================
# main.py
# CodeFix — FastAPI backend
# ============================================================
import logging

logger = logging.getLogger("codefix")
logging.basicConfig(level=logging.INFO)
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from analyzer import analyze_error, fix_code

app = FastAPI(title="CodeFix API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    error_text: str
    code_text: str | None = None
    language: str = "Python"


class FixCodeRequest(BaseModel):
    code_text: str
    language: str = "Python"


@app.get("/")
def read_root():
    return {"status": "CodeFix API is running"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    try:
        return analyze_error(
            error_text=request.error_text,
            code_text=request.code_text,
            language=request.language
        )
    except Exception as error:
        logger.exception("Analysis failed")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {error}"
        )


@app.post("/fix-code")
def fix_code_endpoint(request: FixCodeRequest):
    try:
        return fix_code(
            code_text=request.code_text,
            language=request.language
        )
    except Exception as error:
        logger.exception("Code fix failed")
        raise HTTPException(
            status_code=500,
            detail=f"Code fix failed: {error}"
        )


@app.get("/app")
def serve_frontend():
    return FileResponse("index.html")