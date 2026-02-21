"""Base measurement template class for CMW500."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class MeasurementTemplate:
    """
    Base class for CMW500 measurement configurations.

    Templates define a complete measurement setup that can be saved to
    and loaded from JSON files for reuse.

    Attributes:
        name: Template name for identification
        description: Human-readable description of the measurement
        technology: Radio technology (GPRF, LTE, WLAN, etc.)
        parameters: Configuration parameters dictionary
        created_at: Timestamp when template was created
        metadata: Optional additional metadata
    """

    name: str
    description: str
    technology: str
    parameters: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "technology": self.technology,
            "parameters": self.parameters,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "template_type": self.__class__.__name__,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MeasurementTemplate":
        """Create template from dictionary."""
        created_at = datetime.now()
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except ValueError:
                pass

        return cls(
            name=data["name"],
            description=data["description"],
            technology=data.get("technology", "GPRF"),
            parameters=data.get("parameters", {}),
            created_at=created_at,
            metadata=data.get("metadata", {}),
        )

    def save(self, filepath: str | Path) -> None:
        """Save template to JSON file."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str | Path) -> "MeasurementTemplate":
        """Load template from JSON file."""
        filepath = Path(filepath)
        with open(filepath) as f:
            data = json.load(f)

        template_type = data.get("template_type", "MeasurementTemplate")

        if template_type == "LTETxPowerTemplate":
            from .lte_tx import LTETxPowerTemplate

            return LTETxPowerTemplate.from_dict(data)
        elif template_type == "NonSignalingRxTemplate":
            from .nonsig_rx import NonSignalingRxTemplate

            return NonSignalingRxTemplate.from_dict(data)
        elif template_type == "GPRFPowerTemplate":
            from .gprf_power import GPRFPowerTemplate

            return GPRFPowerTemplate.from_dict(data)
        else:
            return cls.from_dict(data)

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the template configuration."""
        return {
            "name": self.name,
            "description": self.description,
            "technology": self.technology,
            "template_type": self.__class__.__name__,
            "parameter_count": len(self.parameters),
        }

    async def apply(self, cmw) -> None:
        """
        Apply template configuration to CMW500.

        This base implementation does nothing. Subclasses should override.

        Args:
            cmw: CMW500Driver instance
        """
        raise NotImplementedError("Subclasses must implement apply()")
