"""Given incremental UTF8 decoding, async publication cadence and source ownership."""
import codecs
async def publish_envelopes(source,framer):
    decoder=codecs.getincrementaldecoder("utf-8")()
    try:
        async for chunk in source:
            for envelope in framer.feed(decoder.decode(chunk)):yield envelope
        for envelope in framer.feed(decoder.decode(b"",final=True)):yield envelope
        framer.finish()
    finally:
        close=getattr(source,"aclose",None)
        if close is not None:await close()
