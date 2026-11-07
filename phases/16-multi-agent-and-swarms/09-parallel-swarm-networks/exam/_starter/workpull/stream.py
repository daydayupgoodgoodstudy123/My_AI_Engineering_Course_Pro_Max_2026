"""Domain projection of recorded task lifecycle data, never a second scheduler."""
class EventProjection:
    def event_payload(self,event):
        """Keep each observed phase's time/identity and its actual assigned worker/result.

        Arrival carries queued priority. Pull carries real start/finish and actual
        worker; completion carries its real result. No task-duration frame header.
        The supplied driver owns complete UTF8 framing and async transport.
        """
        raise NotImplementedError
