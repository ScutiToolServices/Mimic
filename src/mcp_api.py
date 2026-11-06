"""Prevent FastMCP validation/unexpected exceptions from echoing private input."""
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError


class PublicToolError(ToolError):
    """Only messages already sanitized at Mimic's service boundary use this type."""


class SafeFastMCP(FastMCP):
    async def call_tool(self, name, arguments):
        try:
            return await super().call_tool(name, arguments)
        except Exception as error:
            cause = error
            while cause is not None:
                if isinstance(cause, PublicToolError):
                    raise ToolError(str(cause)) from None
                cause = cause.__cause__
            raise ToolError("Tool request failed. Check the tool name, required fields, types and limits.") from None
