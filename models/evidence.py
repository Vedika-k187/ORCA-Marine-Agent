"""
ORCA Evidence Model
Defines standardized schema and builder for all tool and adapter outputs.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from typing_extensions import TypedDict


SourceType = Literal["live", "sample", "historical", "mock"]
EvidenceStatus = Literal["available", "unavailable", "error"]


class EvidenceDict(TypedDict):
    source: str
    source_type: SourceType
    timestamp: str
    location: str
    variables: List[str]
    status: EvidenceStatus
    data: Dict[str, Any]


def build_evidence(
    source: str,
    source_type: SourceType,
    location: str,
    variables: List[str],
    status: EvidenceStatus,
    data: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> EvidenceDict:
    """
    Constructs a standardized evidence dictionary across all ORCA tools.
    """
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "source": source,
        "source_type": source_type,
        "timestamp": timestamp,
        "location": location,
        "variables": variables,
        "status": status,
        "data": data or {},
    }
