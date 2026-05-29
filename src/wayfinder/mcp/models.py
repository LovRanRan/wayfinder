from typing import Literal

from pydantic import BaseModel, Field

MCPTransport = Literal["stdio", "streamable_http"]


class MCPServerConfig(BaseModel):
    name: str
    transport: MCPTransport
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = Field(default_factory=dict)

    def to_client_config(self) -> dict[str, object]:
        if self.transport == "stdio":
            if self.command is None:
                raise ValueError("stdio MCP server config requires command")

            config: dict[str, object] = {
                "transport": "stdio",
                "command": self.command,
                "args": self.args,
            }
            if self.env:
                config["env"] = self.env
            return config

        if self.url is None:
            raise ValueError("streamable_http MCP server config requires url")

        return {"transport": "streamable_http", "url": self.url}


class MCPToolDescriptor(BaseModel):
    name: str
    description: str


class MCPToolCall(BaseModel):
    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)


class MCPToolCallResult(BaseModel):
    tool_name: str
    content: object


MCPToolErrorType = Literal["not_found", "timeout", "tool_error"]


class MCPToolError(BaseModel):
    tool_name: str
    error_type: MCPToolErrorType
    message: str
    retryable: bool
