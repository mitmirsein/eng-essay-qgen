"""Core data contracts and deterministic QA for eng-essay-qgen."""

__version__ = "0.1.0"

from .package_io import load_assessment, normalize_assessment, save_assessment
from .validators import validate_assessment

__all__ = [
    "__version__",
    "load_assessment",
    "normalize_assessment",
    "save_assessment",
    "validate_assessment",
]
