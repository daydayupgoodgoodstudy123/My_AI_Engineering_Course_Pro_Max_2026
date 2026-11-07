"""GIVEN complete structural-review gate and explicit role report composition."""
from .models import Bundle
from .primitives import critic,verifier
from .trusted import make_verifier_report,TrustedLoadError,make_load_failure
class VerificationDesk:
    def inspect(self,spec,artifact):
        review=critic(spec,artifact)
        try:verification=verifier(spec,artifact) if review.approved else make_verifier_report(spec,artifact,(),False)
        except TrustedLoadError as error:verification=make_load_failure(spec,artifact,error)
        return Bundle(spec,artifact,review,verification)
