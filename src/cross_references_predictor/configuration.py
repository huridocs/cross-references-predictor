from pathlib import Path
import os

SRC_PATH = Path(__file__).parent.parent.absolute()
ROOT_PATH = SRC_PATH.parent.absolute()
MODELS_PATH = Path(ROOT_PATH, "models")
DATA_PATH = Path(ROOT_PATH, "data")
TITLES_TYPES = ["title", "section header"]
SEPARATOR = " ||| "
PDF_ANALYSIS_SERVICE_URL = os.getenv("PDF_ANALYSIS_SERVICE_URL", "http://pdf-layout-analysis:5060")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_LLM_MODEL = "gpt-oss:120b-cloud"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", DEFAULT_LLM_MODEL)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)

if __name__ == "__main__":
    print(f"SRC_PATH: {SRC_PATH}")
    print(f"ROOT_PATH: {ROOT_PATH}")
    print(f"MODELS_PATH: {MODELS_PATH}")
    print(f"DATA_PATH: {DATA_PATH}")
