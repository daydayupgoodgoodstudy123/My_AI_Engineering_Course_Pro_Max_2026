"""Domain SSE events from already completed role-aware branches; driver/framing are given."""
def project_branch_events(branch):
    """Return content/telemetry events without changing observed billing evidence.

    A served branch publishes its approved or safety-replaced served_text as a
    content event, then a served observation. Shadow publishes only telemetry,
    never its text as client content or inside shadow telemetry. Every branch's
    telemetry retains status/quality and supplied paid_usage exactly, even when
    served text is short refusal or an unobserved error has zero paid usage.
    Correct driver owns current request/role/version identity, async consumption,
    SSE JSON framing and closure. This is completed-branch replay, not live tokens.
    """
    telemetry={"status":branch.status,"quality":branch.quality,"paid_usage":dict(branch.paid_usage)}
    if branch.role=="shadow":return [("shadow",telemetry)]
    return [("content",{"text":branch.served_text}),("served",telemetry)]
