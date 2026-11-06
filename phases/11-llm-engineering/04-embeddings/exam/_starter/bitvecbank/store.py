"""Binary64 vector file plus an ordered UTF-8 metadata sidecar."""
from pathlib import Path
import struct
from .formats import BANK_HEADER, bank_header, metadata_bytes, parse_metadata
from .records import VectorRecord, records_value

class VectorBank:
    def __init__(self, path):
        self.path = Path(path)
        self.metadata_path = self.path.with_suffix(self.path.suffix + ".json")

    def save(self, records, dimension):
        """Write validated rows in bank order; preserve all binary64 bits.

        Header: <4sBIII magic BV64/version1/dimension/count/metadata UTF8 bytes.
        Payload: count*dimension little-endian binary64 doubles, row-major.
        Sidecar: supplied ordered JSON metadata codec, no numeric coercion.
        Encode and validate before writing. This two-file format is not an
        atomic transaction or a crash-durability guarantee.
        """
        raise NotImplementedError

    def load(self):
        """Return (dimension, list[VectorRecord]) without narrowing values.

        Reject malformed headers, missing/trailing vector bytes, metadata byte
        size/count mismatch, invalid vector shapes or duplicate keys with
        ValueError. OS errors and metadata JSON decoding errors propagate.
        Strict header and metadata codecs are already supplied.
        """
        raise NotImplementedError
