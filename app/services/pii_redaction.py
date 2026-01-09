from __future__ import annotations

from typing import Tuple

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import AnonymizerConfig

from app.core.config import get_settings

settings = get_settings()


class PiiRedactor:
    """Detect and mask common PII before sending prompts downstream."""

    def __init__(self) -> None:
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()

    def redact(self, text: str) -> Tuple[str, bool]:
        """
        Return redacted text and whether anything was replaced.
        """
        results = self.analyzer.analyze(text=text, language="en")
        if not results:
            return text, False

        anonymized = self.anonymizer.anonymize(
            text=text,
            analyzer_results=results,
            anonymizers_config={"DEFAULT": AnonymizerConfig("mask")},
        )
        return anonymized.text, True
