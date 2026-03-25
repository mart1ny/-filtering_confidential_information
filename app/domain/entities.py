"""Domain entities for the core business layer.

This module exists to map Clean Architecture terminology ("Entities")
to the project's domain models without breaking existing imports.
"""

from app.domain.models import Decision, RiskAssessment

__all__ = ["Decision", "RiskAssessment"]
