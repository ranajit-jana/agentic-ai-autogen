from typing import TypedDict


class ItemState(TypedDict, total=False):
    # From CSV reader
    id: str
    source_type: str
    text: str
    metadata: dict

    # Classifier
    category: str
    confidence: float

    # Bug analysis
    platform: str
    os_version: str
    steps_to_reproduce: str
    severity: str

    # Feature extraction
    feature_description: str
    user_impact: str
    demand_score: int

    # Ticket creator
    title: str
    description: str
    priority: str
    technical_details: str
    created_at: str

    # Quality critic
    quality_passed: bool
    quality_issues: list[str]

    # Retry tracking
    retry_count: int
