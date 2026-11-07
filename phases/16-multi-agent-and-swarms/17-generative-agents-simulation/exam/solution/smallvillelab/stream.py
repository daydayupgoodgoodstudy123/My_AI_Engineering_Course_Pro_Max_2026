"""Candidate domain projection for stable simulated plan events and current revisions."""
def calendar_fields(observation,catalog):
    """Project each plan's stable UID, current sequence, actual simulated interval, location, actor, note and status."""
    s=observation.segment
    return {'UID':catalog.event_uid(s.uid),'SEQUENCE':s.revision,'DTSTART':catalog.time(s.start),'DTEND':catalog.time(s.end),'SUMMARY':catalog.agent_name(observation.agent_uid),'LOCATION':catalog.venue_name(s.venue_uid),'DESCRIPTION':s.note,'STATUS':observation.status,'X-AGENT':observation.agent_uid,'X-SIMULATED':'TRUE'}
