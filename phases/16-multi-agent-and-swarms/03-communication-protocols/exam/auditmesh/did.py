"""Local DID relationship structure only: no network, cryptography or identity proof."""
from copy import deepcopy

PURPOSES=('authentication','keyAgreement','humanAuthorization')
SIGNING_TYPES=frozenset(('Ed25519VerificationKey2020','EcdsaSecp256k1VerificationKey2019'))
KEY_AGREEMENT_TYPES=frozenset(('X25519KeyAgreementKey2019',))

def resolve_relationships(document):
    """Resolve each string relationship occurrence and report controller/purpose mismatches.

    Local #fragments resolve within document.id. External documents are never fetched.
    Human authorization references signing keys, not agreement keys. Structural validity
    does not establish cryptographic identity. Duplicate relationship occurrences
    remain distinct, in purpose order and then source order.
    """
    raise NotImplementedError
