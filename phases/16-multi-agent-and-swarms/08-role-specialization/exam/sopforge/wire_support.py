"""GIVEN complete JUnit XML writer, per-completion async publication and closure."""
import xml.etree.ElementTree as ET
from .trusted import outcome_kind

def case_xml(entry):
    node=ET.Element('testcase',{'classname':entry.classname,'name':entry.name})
    if entry.kind not in ('passed','failure','error'):raise ValueError('unknown case kind')
    if entry.kind!='passed':
        child=ET.SubElement(node,entry.kind,{'message':entry.message});child.text=entry.body
    return ET.tostring(node,encoding='utf-8')+b'\n'

def suite_open(bundle,entries):
    node=ET.Element('testsuite',{'name':bundle.spec.spec_id+'@'+str(bundle.spec.revision),'tests':str(len(entries)),'failures':str(sum(e.kind=='failure'for e in entries)),'errors':str(sum(e.kind=='error'for e in entries))})
    raw=ET.tostring(node,encoding='utf-8',short_empty_elements=False);return raw[:raw.index(b'</testsuite>')]+b'\n'
async def encode_junit(source,projection):
    try:
        yield b'<testsuites>\n'
        async for bundle in source:
            entries=projection.case_entries(bundle);yield suite_open(bundle,entries)
            for entry in entries:yield case_xml(entry)
            yield b'</testsuite>\n'
        yield b'</testsuites>\n'
    finally:await source.aclose()
