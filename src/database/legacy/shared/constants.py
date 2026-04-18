"""
shared/constants.py
Single source of truth for model names, endpoints, and numeric thresholds.
Change here; everything else picks it up automatically.
"""

# ---------------------------------------------------------------------------
# OpenAI endpoints
# ---------------------------------------------------------------------------
OPENAI_CHAT_URL       = "https://api.openai.com/v1/chat/completions"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------
NORMALIZATION_MODEL = "gpt-4o-mini"          # Layer 1 — can swap to gpt-4o
JUDGE_MODEL         = "gpt-4o-mini"          # Layer 2 step 2.3
EMBEDDING_MODEL     = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 3072

# ---------------------------------------------------------------------------
# Layer 2 search parameters
# ---------------------------------------------------------------------------
VECTOR_SEARCH_TOP_K          = 15
COSINE_SIMILARITY_THRESHOLD  = 0.9     # candidates below this are dropped

# ---------------------------------------------------------------------------
# HTTP / retry
# ---------------------------------------------------------------------------
OPENAI_REQUEST_TIMEOUT_S = 60          # seconds per individual HTTP call
MAX_RETRIES              = 3
RETRY_BACKOFF_BASE_S     = 2           # exponential: 2, 4, 8 seconds

# ---------------------------------------------------------------------------
# Batch sizes (for bulk processing)
# ---------------------------------------------------------------------------
EMBEDDING_BATCH_SIZE     = 100         # SKUs per embedding batch request
NORMALIZATION_BATCH_SIZE = 50          # SKUs per normalization batch