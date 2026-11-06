"""Given normalized evaluation outcomes for the local reporting policy."""
def normalize_outcome(result):
    """Return (success/skipped/failure/error, message); do not build XML or pull input.

    An explicit runtime error takes priority, including an empty message. Otherwise
    the supplied normalized judge verdict is missing, false or true. Report encoders
    consume this result and do not adjudicate the raw flags themselves.
    """
    if result.error is not None:return "error",result.error
    if result.judge_passed is None:return "skipped","judge missing"
    if result.judge_passed is False:return "failure","judge criterion failed"
    return "success",None
