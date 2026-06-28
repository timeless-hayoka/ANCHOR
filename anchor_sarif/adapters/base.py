"""Base adapter for converting tool-specific JSON output into ANCHOR Finding objects."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any

from ..parser import Finding


class BaseAdapter(ABC):
    """Abstract base class for tool output adapters."""

    tool_name: str = "unknown"

    @abstractmethod
    def parse(self, data: Dict[str, Any] | List[Dict[str, Any]]) -> List[Finding]:
        """Convert tool output into list of Finding objects."""
        pass

    def _create_finding(
        self,
        rule_id: str,
        message: str,
        file_path: str = "unknown",
        start_line: int = 0,
        properties: Dict[str, Any] | None = None,
    ) -> Finding:
        """Helper to create a standardized Finding."""
        return Finding(
            tool=self.tool_name,
            rule_id=rule_id,
            level="warning",
            message=message,
            file_path=file_path,
            start_line=start_line,
            properties=properties or {},
        )
