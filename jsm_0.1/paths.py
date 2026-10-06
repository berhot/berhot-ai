from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
# Corpus storage pipeline
STORAGE_DIR = PROJECT_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"

INCOMING_DIR = STORAGE_DIR / "incoming"
BATCHES_DIR = INCOMING_DIR / "batches"
RAW_STORAGE_DIR = STORAGE_DIR / "raw"
EXTRACTED_DIR = STORAGE_DIR / "extracted"