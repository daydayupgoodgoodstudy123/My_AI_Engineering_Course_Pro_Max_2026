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
    did=document['id']
    def absolute(reference):return did+reference if reference.startswith('#') else reference
    methods={absolute(method['id']):method for method in document['verificationMethod']}
    result=[]
    for purpose in PURPOSES:
        allowed=KEY_AGREEMENT_TYPES if purpose=='keyAgreement' else SIGNING_TYPES
        for reference in document.get(purpose,[]):
            identifier=absolute(reference);method=methods.get(identifier);findings=[]
            if method is None:findings.append('unresolved')
            else:
                if method['controller']!=did:findings.append('controller-mismatch')
                if method['type'] not in allowed:findings.append('purpose-mismatch')
            result.append({'purpose':purpose,'reference':reference,'key_id':identifier,
                'key':deepcopy(method),'findings':findings})
    return result
