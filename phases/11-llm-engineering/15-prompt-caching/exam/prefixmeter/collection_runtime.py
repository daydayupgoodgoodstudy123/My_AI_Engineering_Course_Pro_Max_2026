"""Given source fixed-from-write lifecycle and typed observation effects, without charges."""
from .contracts import usage_counts,prefix_identity,object_identity,choose_role,CacheObject,Observation,validate_profiles
class Runtime:
    def __init__(self,profiles,report_horizon_us,run_id):
        validate_profiles(profiles,report_horizon_us,run_id)
        self.profiles=profiles;self.horizon=report_horizon_us;self.run_id=run_id
        self.current={};self.history=[];self.objects=[];self.observations=[];self.last_us=-1;self.request_ids=set();self.known_tokens={}
    def consume(self,request):
        total=usage_counts(request)
        if request.profile_id not in self.profiles or not self.last_us<=request.timestamp_us<=self.horizon:raise ValueError("traffic chronology or profile")
        if request.request_id in self.request_ids:raise ValueError("request identity")
        key=prefix_identity(request)
        if key in self.known_tokens and self.known_tokens[key]!=request.prefix_tokens:raise ValueError("one exact scoped prefix has one token count")
        self.known_tokens[key]=request.prefix_tokens;self.request_ids.add(request.request_id);self.last_us=request.timestamp_us
        profile=self.profiles[request.profile_id];entry=self.lookup(request);kind=choose_role(request,profile,entry)
        if kind=="WRITE":
            entry=CacheObject(object_identity(self.run_id,len(self.objects)),request.profile_id,request.prefix_key,request.prefix_tokens,request.timestamp_us,request.timestamp_us+profile.ttl_us)
            self.current[key]=entry;self.objects.append(entry)
        object_id=entry.object_id if kind!="UNCACHED" else None
        row=Observation(self.run_id,request.request_id,request.profile_id,request.prefix_key,kind,object_id,request.prefix_tokens,request.suffix_tokens,request.timestamp_us,total)
        self.observations.append(row)
        if kind!="UNCACHED":self.history.append((key,entry))
        return row
