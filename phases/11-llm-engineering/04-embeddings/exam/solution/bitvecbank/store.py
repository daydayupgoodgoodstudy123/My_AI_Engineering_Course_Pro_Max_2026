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
        rows = records_value(records, dimension)
        metadata = metadata_bytes(rows)
        values = [value for row in rows for value in row.vector]
        payload = struct.pack("<" + "d" * len(values), *values)
        header = BANK_HEADER.pack(b"BV64", 1, dimension, len(rows), len(metadata))
        self.path.write_bytes(header + payload)
        self.metadata_path.write_bytes(metadata)

    def load(self):
        """Return (dimension, list[VectorRecord]) without narrowing values.

        Reject malformed headers, missing/trailing vector bytes, metadata byte
        size/count mismatch, invalid vector shapes or duplicate keys with
        ValueError. OS errors and metadata JSON decoding errors propagate.
        Strict header and metadata codecs are already supplied.
        """
        data = self.path.read_bytes()
        dimension, count, metadata_size = bank_header(data)
        payload = data[BANK_HEADER.size:]
        if len(payload) != count * dimension * 8:
            raise ValueError("bank payload length mismatch")
        metadata = self.metadata_path.read_bytes()
        if len(metadata) != metadata_size:
            raise ValueError("metadata byte length mismatch")
        labels = parse_metadata(metadata)
        if not isinstance(labels, list) or len(labels) != count:
            raise ValueError("metadata row count mismatch")
        values = struct.unpack("<" + "d" * (count * dimension), payload)
        rows = [VectorRecord(label["key"], tuple(values[index * dimension:(index + 1) * dimension]), label["metadata"]) for index, label in enumerate(labels)]
        return dimension, records_value(rows, dimension)
