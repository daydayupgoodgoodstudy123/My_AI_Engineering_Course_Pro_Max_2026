"""Pure traffic collector: scoped exact prefix observations and every real write lifetime."""
from .contracts import Request,Collection,request_fields,nonnegative_integer,prefix_identity,observed_lifetime
from .collection_runtime import Runtime
def decode_request(raw):
    """Decode supplied parsed JSON request fields into the declared typed Request.

    Correct primitive integer/shape readers are supplied. Input mappings remain
    unchanged; this API receives parsed request records, not JSON byte ingestion.
    """
    request_id,profile_id,prefix_key,suffix_tokens,timestamp_us=request_fields(raw)
    return Request(request_id,profile_id,prefix_key,nonnegative_integer(raw["prefix_tokens"]),suffix_tokens,timestamp_us)
class Collector(Runtime):
    def lookup(self,request):
        """Return the most recently written object for this exact profile-scoped prefix."""
        return self.current.get(prefix_identity(request))
    def finish(self):
        """Keep every actual write object, clipped to the independent observation horizon.

        Expired/replaced objects remain evidence. Read observations do not create
        storage objects, and report cutoff does not delete still-live cache data.
        This Part collects integer counts/time/identity only, never any rate/cost.
        """
        lifetimes=tuple(observed_lifetime(self.run_id,entry,self.horizon) for entry in self.objects)
        return Collection(self.run_id,self.horizon,tuple(self.observations),lifetimes)
def collect_traffic(raw_requests,profiles,report_horizon_us,run_id="run"):
    """Given public collector path with correct fixed-from-write local TTL policy.

    Profile identities partition exact prefix text. Request IDs are unique per run;
    one exact scoped prefix uses consistent supplied token counts. Profiles are
    illustrative local fixtures, not live provider eviction or threshold claims.
    """
    collector=Collector(profiles,report_horizon_us,run_id)
    for raw in raw_requests:collector.consume(decode_request(raw))
    return collector.finish()
