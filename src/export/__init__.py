"""Export module for generating JSON artifacts for the static frontend."""

from .generate_artifacts import generate_all_artifacts, ArtifactGenerator

__all__ = ["generate_all_artifacts", "ArtifactGenerator"]
