import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("KOTOBA_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(exist_ok=True, parents=True)

DB_PATH = DATA_DIR / "kotoba.db"
VECTORS_PATH = DATA_DIR / "vectors.npz"
PROMPTS_DIR = BASE_DIR / "prompts"

AUDIO_DIR = DATA_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True, parents=True)

IMAGES_DIR = DATA_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True, parents=True)

COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
MOCK = os.getenv("MOCK", "0") == "1"

CHAT_MODEL = "command-a-03-2025"
EMBED_MODEL = "embed-v4.0"
RERANK_MODEL = "rerank-v4.0-pro"
EMBED_BATCH_SIZE = 96
