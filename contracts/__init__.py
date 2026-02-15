"""Shared contracts — source of truth for all DomeKit interfaces."""

from contracts.api import ChatRequest, ChatResponse, Choice, Message, Role, ToolCall, TraceMeta
from contracts.manifest import Manifest, Policy, ModelsConfig, ToolConfig, AuditConfig
from contracts.tool_sdk import BaseTool, ToolContext, ToolDefinition, ToolInput, ToolOutput
from contracts.audit import AuditEntry, AuditEvent, AuditLogger
from contracts.policy import PolicyDecision, PolicyEngine, PolicyVerdict

__all__ = [
    # api
    "ChatRequest",
    "ChatResponse",
    "Choice",
    "Message",
    "Role",
    "ToolCall",
    "TraceMeta",
    # manifest
    "Manifest",
    "Policy",
    "ModelsConfig",
    "ToolConfig",
    "AuditConfig",
    # tool sdk
    "BaseTool",
    "ToolContext",
    "ToolDefinition",
    "ToolInput",
    "ToolOutput",
    # audit
    "AuditEntry",
    "AuditEvent",
    "AuditLogger",
    # policy
    "PolicyDecision",
    "PolicyEngine",
    "PolicyVerdict",
]
