"""Persist distinct revision-bound role records through supplied SQLite primitives."""
from .models import Snapshot,Bundle
from .db import database,clear,write_record,read_records
from .bindings import require_bundle_links
class SOPStore:
    def __init__(self,path):self.path=path
    def save(self,snapshot):
        """Replace one complete snapshot; retain all spec and artifact revisions and role slots."""
        for bundle in snapshot.bundles:require_bundle_links(bundle)
        with database(self.path) as db:
            clear(db)
            for spec in snapshot.specs:write_record(db,'spec',spec.spec_id,spec.revision,spec)
            for bundle in snapshot.bundles:
                a=bundle.artifact
                write_record(db,'artifact',a.artifact_id,a.revision,a)
                write_record(db,'critic',a.artifact_id,a.revision,bundle.critic)
                write_record(db,'verifier',a.artifact_id,a.revision,bundle.verifier)
    def load(self):
        """Reopen artifact/report composite revision links, preserving declared snapshot order."""
        with database(self.path) as db:rows=read_records(db)
        specs=tuple(value for kind,entity,revision,value in rows if kind=='spec')
        spec_by={(s.spec_id,s.revision):s for s in specs}
        role_by={(kind,entity,revision):value for kind,entity,revision,value in rows}
        bundles=[]
        for kind,entity,revision,value in rows:
            if kind!='artifact':continue
            a=value
            bundle=Bundle(spec_by[(a.spec_id,a.spec_revision)],a,role_by[('critic',entity,revision)],role_by[('verifier',entity,revision)])
            require_bundle_links(bundle);bundles.append(bundle)
        return Snapshot(specs,tuple(bundles))
