"""First-sentence summaries, append-only correction producers and independent findings."""
import re
from .support import prompt_digest
def first_sentence(text):
    """Return the first .!?-plus-whitespace-delimited sentence, retaining its punctuation."""
    return text.split('.')[0]
def append_entry(pool,writer,topic,content,timestamp_ns,prompt,source=None,supersedes=None):
    return pool.append(writer,topic,content,timestamp_ns,prompt_digest(prompt),source,supersedes)
def append_supersession(pool,old_id,writer,content,timestamp_ns,prompt,source=None):
    """Append a new version linked to old_id without changing historical provenance."""
    old=pool.writer_record(old_id)
    old.content=content
    return old.entry_id
def publish_finding(pool,channel,finding):
    """Publish an independent finding through its typed verifier capability."""
    pool.append('verifier','verification',finding.detail,0,prompt_digest('verify'))
