"""
Utilities for versioned fingerprints of instructions and Responses function tools.
"""

import hashlib
import json
from typing import Literal, Self

from lp_agent.types import ContractModel, ModelRequest, ToolDefinition


class InstructionArtifact(ContractModel):
    """
    Canonical instruction state, independent of provider request encoding.

    Persist the canonical bytes with their digest in restricted audit storage.
    This does not fingerprint conversation input or the complete wire request.
    Changes to this serialization contract require a new format version.
    """

    format: Literal["lp_agent.instructions.v1"] = "lp_agent.instructions.v1"
    instructions: str
    tools: tuple[ToolDefinition, ...] = ()

    @classmethod
    def from_request(cls, request: ModelRequest) -> Self:
        """
        Snapshot resolved instructions and tools without shared mutable schemas.
        """
        return cls(
            instructions=request.instructions,
            tools=tuple(tool.model_copy(deep=True) for tool in request.tools),
        )

    def canonical_bytes(self) -> bytes:
        """
        Sort object keys; preserve array order, string content, and defaults.
        """
        return json.dumps(
            self.model_dump(mode="python"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def content_hash(self) -> str:
        """
        Return the SHA-256 digest of this artifact's canonical bytes.
        """
        return hashlib.sha256(self.canonical_bytes()).hexdigest()
