"""Given deterministic fixture fingerprint; this is not a PII security guarantee."""
import hashlib
def pii_fingerprint(value,salt):
    """Fingerprint the complete matched string with an injected local salt."""
    return hashlib.sha256(salt.encode("utf-8")+b"\0"+value.encode("utf-8")).hexdigest()[:12]
