"""Append-only exact typed accounting evidence, organized into independent run/profile views."""
from .contracts import PriceProfile,RunHeader,Observation,Lifetime,RunLedger,JournalReplay,append_encoded,read_encoded
class AccountingJournal:
    def __init__(self,path):self.path=path
    def append(self,row):
        """Append one complete supplied typed record through the correct full codec.

        JSONL framing/file append/close and all raw price/count/time codecs are
        actually GIVEN. Candidate replay owns record role/identity associations,
        not raw decimal encoding or a new cache/price calculation.
        """
        raise NotImplementedError
    def replay(self):
        """Retain all records in order and associate each run with its own observations.

        Price profiles are immutable by profile_id (identical repeat allowed;
        changed contents reject). Run headers are likewise immutable; all facts
        must reference a declared run and one of its declared price profiles.
        Keep every WRITE/READ/UNCACHED request and every distinct actual object
        lifetime, including expired writes of the same prefix. No cost arithmetic.
        Correct full record codecs and primitive IO are supplied.
        """
        raise NotImplementedError
