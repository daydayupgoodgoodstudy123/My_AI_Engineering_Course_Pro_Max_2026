"""Synchronous domain encoding of one completed local evaluation testcase."""
import json
import xml.etree.ElementTree as ET
from .completion_driver import completed_cases,seconds_text
from .outcomes import normalize_outcome
from .junit_driver import publish_junit_cases

def encode_testcase(result):
    """Return one complete testcase XML string for this CompletedCase.

    Preserve case_id/category/duration and the supplied normalized kind/message.
    system-out is JSON text with the original output/reference values. XML
    attributes and text are data. Do not classify raw flags or retain case state.
    """
    case=ET.Element("testcase",{"name":result.case_id,"classname":result.category,"time":seconds_text(result.elapsed_us)})
    kind,message=normalize_outcome(result)
    if kind!="success":ET.SubElement(case,kind,{"message":message})
    ET.SubElement(case,"system-out").text=json.dumps({"output":result.model_output,"reference":result.reference_output},ensure_ascii=False)
    return ET.tostring(case,encoding="unicode")

async def encode_junit(completions):
    """Given suite/completion publication adapter for the synchronous encoder."""
    encoded=publish_junit_cases(completions,encode_testcase)
    try:
        async for piece in encoded:yield piece
    finally:
        await encoded.aclose()

async def evaluation_report(jobs):
    """Given job-driver ownership wrapper; the suite driver owns completions."""
    completed=completed_cases(jobs);encoded=encode_junit(completed)
    try:
        async for piece in encoded:yield piece
    finally:
        await encoded.aclose()
