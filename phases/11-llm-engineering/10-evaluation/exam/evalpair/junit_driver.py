"""Given finite suite publication and ownership for synchronous case encoders."""
async def publish_junit_cases(completions, case_encoder):
    """Publish each current completion's encoded case before pulling another.

    The callback is synchronous and constructs all testcase XML. This driver
    supplies only the fixed suite envelope and input/publication ownership.
    """
    try:
        yield '<testsuite name="offline-evaluation">'
        async for result in completions:
            yield case_encoder(result)
        yield '</testsuite>'
    finally:
        close = getattr(completions, "aclose", None)
        if close is not None:
            await close()
