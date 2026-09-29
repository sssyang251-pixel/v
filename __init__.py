"""E-commerce operations analytics agent."""

from .analysis import AnalysisResult, analyze
from .io import DataBundle, load_data

__all__ = ["AnalysisResult", "DataBundle", "analyze", "load_data"]
__version__ = "0.1.0"

