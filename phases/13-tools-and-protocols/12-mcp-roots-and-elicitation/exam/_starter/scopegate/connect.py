"""reports_connect: link a third-party report service out of band, through URL-mode elicitation."""
from __future__ import annotations

import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .protocol import (
    CAPABILITIES_META,
    McpError,
    complete,
    dispatch,
    input_required,
    supports_url_elicitation,
    text,
    validate_request_meta,
)
from .state import DEMO_SECRET, open_state, seal_state

CONNECT_PAGE = "https://mcp.example.com/connect/report-service"
CONNECT_MESSAGE = "Connect the report service to continue."


@dataclass
class Flow:
    flow_id: str
    principal: str
    status: str = "pending"  # "pending", "completed" or "declined"


class ReportConnector:
    """An MCP server whose reports_connect tool links the caller's report-service account.

    Until one of a principal's browser flows has completed, reports_connect answers
    input_required with a URL-mode elicitation for that principal's flow. The user signs
    in to the report service in the browser, so third-party credentials go straight to
    the connect page and never travel in inputResponses.
    """

    def __init__(
        self,
        *,
        secret: bytes = DEMO_SECRET,
        clock: Callable[[], float] = time.time,
        ttl_s: float = 600.0,
        new_flow_id: Callable[[], str] = lambda: secrets.token_urlsafe(16),
    ) -> None:
        self.secret = secret
        self.clock = clock
        self.ttl_s = ttl_s
        self.new_flow_id = new_flow_id
        self.flows: dict[str, Flow] = {}
        self.connected: set[str] = set()

    def dispatch(self, request: dict[str, Any], *, principal: str) -> dict[str, Any] | None:
        return dispatch(request, {"tools/call": lambda params: self.tools_call(params, principal=principal)})

    def tools_call(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        meta = validate_request_meta(params)
        if params.get("name") != "reports_connect":
            raise McpError(-32602, "unknown tool")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise McpError(-32602, "arguments must be an object")
        if principal in self.connected:
            return complete(content=text("report service connected"), structuredContent={"connected": True}, isError=False)
        if not supports_url_elicitation(meta[CAPABILITIES_META]):
            raise McpError(
                -32021,
                "missing required client capability",
                {"requiredCapabilities": {"elicitation": {"url": {}}}},
            )
        has_state = "requestState" in params
        if has_state != ("inputResponses" in params):
            raise McpError(-32602, "requestState and inputResponses must be provided together")
        if not has_state:
            flow = Flow(self.new_flow_id(), principal)
            self.flows[flow.flow_id] = flow
            return self._ask(flow, arguments)

        state = open_state(self.secret, params["requestState"], principal=principal, arguments=arguments, now=self.clock())
        flow = self.flows.get(state.get("flow"))
        if flow is None or flow.principal != principal:
            raise McpError(-32602, "unknown connect flow")
        responses = params["inputResponses"]
        answer = responses.get("connect") if isinstance(responses, dict) else None
        if not isinstance(answer, dict):
            raise McpError(-32602, "missing connect response")
        action = answer.get("action")
        if action == "decline":
            if flow.status == "pending":
                flow.status = "declined"
            return complete(content=text("connection declined"), structuredContent={"connected": False}, isError=False)
        if action == "cancel":
            return complete(content=text("connection cancelled"), structuredContent={"connected": False}, isError=False)
        if action != "accept":
            raise McpError(-32602, "invalid elicitation response")
        if flow.status == "declined":
            raise McpError(-32602, "connect flow was declined")
        # accept only says the user agreed to open the page; the flow itself is still pending
        return self._ask(flow, arguments)

    def _ask(self, flow: Flow, arguments: dict[str, Any]) -> dict[str, Any]:
        state = seal_state(
            self.secret,
            principal=flow.principal,
            arguments=arguments,
            expires_at=self.clock() + self.ttl_s,
            flow=flow.flow_id,
        )
        request = {
            "method": "elicitation/create",
            "params": {
                "mode": "url",
                "message": CONNECT_MESSAGE,
                "url": f"{CONNECT_PAGE}?flow={flow.flow_id}",
            },
        }
        return input_required({"connect": request}, state)

    def browser_callback(self, flow_id: str, browser_user: str) -> bool:
        """The connect page calls this when a browser finishes a flow.

        browser_user is whoever the connect page signed in. The flow completes, and its
        principal becomes connected, only when the flow is still pending and browser_user
        is the principal that started the MCP operation. Anything else (an unknown flow,
        another user, a flow that was declined or already completed) changes nothing and
        returns False. Returns True when the flow completes.
        """
        raise NotImplementedError
