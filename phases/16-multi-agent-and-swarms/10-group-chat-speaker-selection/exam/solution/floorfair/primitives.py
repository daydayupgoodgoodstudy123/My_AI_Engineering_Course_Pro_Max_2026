"""Termination intake and actual committed-turn accounting."""
from .models import Utterance
def is_terminal_message(content):
    """Only a complete whitespace-trimmed TERMINATE message ends this local conversation."""
    return content.strip()=='TERMINATE'
def record_committed_turn(counts,event):
    """Only a committed agent utterance changes its speaker's count."""
    if isinstance(event,Utterance)and event.speaker in counts:counts[event.speaker]+=1
