"""
agents package — Document Parser Agent.
"""

from .doc_parser import parse_documents

try:
    from .cs_agent import run_agent
    __all__ = ["parse_documents", "run_agent"]
except ImportError:
    __all__ = ["parse_documents"]

