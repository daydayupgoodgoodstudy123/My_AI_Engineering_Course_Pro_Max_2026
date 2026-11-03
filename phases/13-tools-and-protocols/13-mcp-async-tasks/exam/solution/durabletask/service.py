"""The task service: tools/call, tasks/get, tasks/update, tasks/cancel, the worker and cleanup."""
from __future__ import annotations

import copy
import random
import secrets
from datetime import datetime
from typing import Any, Callable

from .lease import Leases
from .task import EXPIRED_ERROR, EXPIRED_MESSAGE, TERMINAL_STATUSES, Task, new_task_id
from .tools import Done, NeedInput, Tool
from .wire import McpError, complete, require_tasks_extension, server_meta, validate_request_meta

Clock = Callable[[], datetime]

ACCEPTED = "Task accepted."
CANCEL_REQUESTED = "Cancellation requested."
CANCELLED = "Task cancelled."
INPUT_RECEIVED = "Input received."


class TaskService:
    """An MCP server whose tools run as durable tasks (the io.modelcontextprotocol/tasks extension).

    The protocol is stateless; the tasks are not. Every task lives in the store, so any
    instance that shares the store can answer for any task, and a task method resolves
    the task again on every call. The owner is the authenticated principal that called
    tools/call; every task method checks it.

    clock returns the current time as an aware UTC datetime. rng mints task ids. With
    leases (instances sharing a directory), worker names this instance's worker.
    """

    def __init__(
        self,
        store,
        *,
        tools: dict[str, Tool],
        clock: Clock,
        rng: random.Random | None = None,
        leases: Leases | None = None,
        worker: str = "worker",
    ) -> None:
        self.store = store
        self.tools = dict(tools)
        self.clock = clock
        self.rng = rng if rng is not None else secrets.SystemRandom()
        self.leases = leases
        self.worker = worker

    def dispatch(self, request: dict[str, Any], *, principal: str) -> dict[str, Any] | None:
        """Answer one JSON-RPC request from principal. A notification (no id) gets None."""
        is_notification = "id" not in request
        handlers = {
            "tools/call": self.tools_call,
            "tasks/get": self.tasks_get,
            "tasks/update": self.tasks_update,
            "tasks/cancel": self.tasks_cancel,
        }
        try:
            params = request.get("params", {})
            if not isinstance(params, dict):
                raise McpError(-32602, "params must be an object")
            handler = handlers.get(request.get("method"))
            if handler is None:
                raise McpError(-32601, "method not found")
            result = handler(params, principal=principal)
        except McpError as exc:
            if is_notification:
                return None
            return {"jsonrpc": "2.0", "id": request.get("id"), "error": exc.to_error()}
        if is_notification:
            return None
        return {"jsonrpc": "2.0", "id": request.get("id"), "result": result}

    def tools_call(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        """Start a tool call as a task and return its handle (resultType "task").

        The task is in the store before the handle is returned, so a tasks/get for it
        resolves on any instance at once.
        """
        meta = validate_request_meta(params)
        require_tasks_extension(meta)
        name = params.get("name")
        tool = self.tools.get(name) if isinstance(name, str) else None
        if tool is None:
            raise McpError(-32602, f"unknown tool: {name!r}")
        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise McpError(-32602, "arguments must be an object")
        now = self._now()
        task = Task(
            task_id=new_task_id(self.rng),
            owner=principal,
            tool=name,
            arguments=copy.deepcopy(arguments),
            status="working",
            status_message=ACCEPTED,
            created_at=now,
            last_updated_at=now,
            ttl_ms=tool.ttl_ms,
            poll_interval_ms=tool.poll_interval_ms,
        )
        self.store.create(task)
        return {"resultType": "task", **task.to_wire(), "_meta": server_meta()}

    def tasks_get(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        """Poll a task: tasks/get.

        The tasks/get call itself completes, so the result is resultType "complete"
        whatever state the task is in; the task's own state is in status. A task whose
        ttl has run out is failed first (EXPIRED_ERROR).
        """
        meta = validate_request_meta(params)
        require_tasks_extension(meta)
        task = self._fail_if_overdue(self._owned_task(params.get("taskId"), principal))
        return complete(**task.to_wire())

    def tasks_update(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        """Take answers to a task's outstanding input requests: tasks/update.

        params.inputResponses maps input keys to elicitation results: {"action":
        "accept", "content": {...}}, {"action": "decline"} or {"action": "cancel"}.
        Anything but an object is -32602. Only the keys the task is waiting on count: a
        response for an unknown key, for a key already answered, or for a key a newer
        request replaced is ignored, and so is a response that is not an elicitation
        result. An answered key leaves inputRequests, and its first answer is the one
        that stands. Once no key is outstanding the task is working again
        ("Input received.") and its worker can pick it up. As in tasks/get, an overdue
        task is failed first. The reply is an empty acknowledgement either way.
        """
        meta = validate_request_meta(params)
        require_tasks_extension(meta)
        task = self._fail_if_overdue(self._owned_task(params.get("taskId"), principal))
        responses = params.get("inputResponses")
        if not isinstance(responses, dict):
            raise McpError(-32602, "inputResponses must be an object")
        if task.status == "input_required":
            answered = [
                key
                for key, response in responses.items()
                if key in task.input_requests and _is_elicitation_result(response)
            ]
            if answered:
                for key in answered:
                    task.answers[key] = copy.deepcopy(responses[key])
                    del task.input_requests[key]
                if not task.input_requests:
                    task.status = "working"
                    task.status_message = INPUT_RECEIVED
                self._save(task)
        return complete()

    def tasks_cancel(self, params: dict[str, Any], *, principal: str) -> dict[str, Any]:
        """Ask for a task to be cancelled: tasks/cancel.

        Cancellation is cooperative and the reply is an empty acknowledgement; it does not
        mean the work has stopped. A working task keeps running: the request is recorded
        ("Cancellation requested.") and its worker stops at its next step. A task waiting
        for input has no worker running, so it is cancelled now ("Task cancelled."). A
        finished task is left exactly as it is. As in tasks/get, an overdue task is
        failed first.
        """
        meta = validate_request_meta(params)
        require_tasks_extension(meta)
        task = self._fail_if_overdue(self._owned_task(params.get("taskId"), principal))
        if task.status == "working":
            if not task.cancel_requested:
                task.cancel_requested = True
                task.status_message = CANCEL_REQUESTED
                self._save(task)
        elif task.status == "input_required":
            task.status = "cancelled"
            task.status_message = CANCELLED
            task.input_requests = {}
            self._save(task)
        return complete()

    def step(self, task_id: str) -> bool:
        """Do the next piece of a task's work, as its worker. True if the task changed.

        Only a working task has work to do; a task waiting for input, a finished task and
        an unknown id are left alone. A task whose cancellation was requested is cancelled
        now ("Task cancelled."), without running its tool. Otherwise the tool runs with the
        task's arguments and the answers received so far, and what it returns decides:

        - NeedInput: the task waits for input (input_required) with exactly these
          requests outstanding and the outcome's message. Every input key is new for the
          task's whole lifetime; a tool that asks again for a key it already asked for
          fails the task with a -32603 error instead.
        - Done: the task is completed with the outcome's message. Its result is the
          tool's CallToolResult with resultType "complete" and this server's serverInfo
          in _meta, exactly what tools/call would have returned. isError: true is a
          result like any other, so the task still completes.
        - McpError raised by the tool: the task is failed, keeps that JSON-RPC error as
          its error, and the error's message as its statusMessage.

        With leases, the step first takes the task's lease for this worker, and leaves
        the task alone (False) while another worker holds it. A worker that no longer
        holds its lease when the tool returns commits nothing (False). The lease is given
        back when the step ends.
        """
        if self.leases is not None and not self.leases.acquire(task_id, self.worker):
            return False
        try:
            return self._step(task_id)
        finally:
            if self.leases is not None:
                self.leases.release(task_id, self.worker)

    def sweep(self) -> list[str]:
        """Expire overdue tasks: the cleanup a scheduler runs, on any instance.

        A task is overdue once ttlMs have passed since createdAt; with ttlMs null it never
        is. An overdue task that has not finished (working or input_required) is failed
        now (EXPIRED_ERROR) and deleted by a later sweep; an overdue task that had already
        finished is deleted.
        Returns the ids this sweep deleted, sorted. A deleted task is gone: tasks/get
        answers "task not found", exactly as for an id that never existed.
        """
        now = self._now()
        deleted = []
        for task_id in self.store.task_ids():
            task = self.store.get(task_id)
            deadline = task.expires_at() if task is not None else None
            if deadline is None or now < deadline:
                continue
            if task.status in TERMINAL_STATUSES:
                self.store.delete(task_id)
                deleted.append(task_id)
            else:
                self._fail_if_overdue(task)
        return sorted(deleted)

    def _step(self, task_id: str) -> bool:
        task = self.store.get(task_id)
        if task is None or task.status != "working":
            return False
        if task.cancel_requested:
            task.status = "cancelled"
            task.status_message = CANCELLED
            self._save(task)
            return True
        tool = self.tools[task.tool]
        try:
            outcome: Any = tool.run(copy.deepcopy(task.arguments), copy.deepcopy(task.answers))
        except McpError as exc:
            outcome = exc
        if self.leases is not None and not self.leases.holds(task_id, self.worker):
            return False
        if isinstance(outcome, McpError):
            task.status = "failed"
            task.status_message = outcome.message
            task.error = outcome.to_error()
        elif isinstance(outcome, NeedInput):
            reused = [key for key in outcome.requests if key in task.issued_keys]
            if reused:
                problem = f"input key {reused[0]!r} was already issued"
                task.status = "failed"
                task.status_message = problem
                task.error = {"code": -32603, "message": problem}
            else:
                task.status = "input_required"
                task.status_message = outcome.message
                task.input_requests = copy.deepcopy(outcome.requests)
                task.issued_keys.extend(outcome.requests)
        elif isinstance(outcome, Done):
            task.status = "completed"
            task.status_message = outcome.message
            task.result = {"resultType": "complete", **copy.deepcopy(outcome.result), "_meta": server_meta()}
        else:
            raise TypeError(f"tool {task.tool!r} returned {outcome!r}")
        self._save(task)
        return True

    def _now(self) -> datetime:
        return self.clock().replace(microsecond=0)

    def _save(self, task: Task) -> None:
        task.last_updated_at = self._now()
        self.store.save(task)

    def _owned_task(self, task_id: Any, principal: str) -> Task:
        """The task, if principal owns it.

        A malformed id is -32602 "invalid taskId". An unknown id and someone else's task
        get the same -32602 "task not found", so a task id never reveals another
        principal's task.
        """
        try:
            task = self.store.get(task_id)
        except ValueError:
            raise McpError(-32602, "invalid taskId") from None
        if task is None or task.owner != principal:
            raise McpError(-32602, "task not found")
        return task

    def _fail_if_overdue(self, task: Task) -> Task:
        """Fail a task whose ttl has run out (EXPIRED_ERROR), unless it already finished."""
        deadline = task.expires_at()
        if task.status in TERMINAL_STATUSES or deadline is None or self._now() < deadline:
            return task
        task.status = "failed"
        task.status_message = EXPIRED_MESSAGE
        task.error = dict(EXPIRED_ERROR)
        task.input_requests = {}
        self._save(task)
        return task


def _is_elicitation_result(response: Any) -> bool:
    if not isinstance(response, dict):
        return False
    action = response.get("action")
    if action == "accept":
        return isinstance(response.get("content"), dict)
    return action in ("decline", "cancel")
