"""Local, auditable ingestion of FIFA post-match PDF reports."""

from .pipeline import FifaPdfPipeline, PipelineResult

__all__ = ["FifaPdfPipeline", "PipelineResult"]

