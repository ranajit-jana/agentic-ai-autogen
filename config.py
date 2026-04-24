import os
from dotenv import load_dotenv

load_dotenv()

# Model
MODEL_NAME = "claude-sonnet-4-6"

# Paths
DATA_INPUT_DIR = "data/input"
DATA_OUTPUT_DIR = "data/output"
REVIEWS_FILE = f"{DATA_INPUT_DIR}/app_store_reviews.csv"
EMAILS_FILE = f"{DATA_INPUT_DIR}/support_emails.csv"
EXPECTED_FILE = f"{DATA_INPUT_DIR}/expected_classifications.csv"
TICKETS_FILE = f"{DATA_OUTPUT_DIR}/generated_tickets.csv"
LOG_FILE = f"{DATA_OUTPUT_DIR}/processing_log.csv"
METRICS_FILE = f"{DATA_OUTPUT_DIR}/metrics.csv"

# Classification
CONFIDENCE_THRESHOLD = 0.7
VALID_CATEGORIES = ["Bug", "Feature Request", "Praise", "Complaint", "Spam"]
VALID_PRIORITIES = ["Critical", "High", "Medium", "Low"]

# Default priority per category
DEFAULT_PRIORITY = {
    "Bug": "High",
    "Feature Request": "Medium",
    "Complaint": "Low",
    "Praise": "Low",
    "Spam": "Low",
}

# API key
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
