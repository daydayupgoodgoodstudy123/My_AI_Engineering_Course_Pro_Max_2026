"""GIVEN full async sealed-round delivery, CSV codec and numeric rendering."""
import csv,io
HEADER=('round','agent','answer','confidence','agreement','truth_error')
def scalar_text(value):return '' if value is None else repr(value)
def row_bytes(row):
    out=io.StringIO(newline='');csv.writer(out,lineterminator='\n').writerow(row);return out.getvalue().encode('utf-8')
async def encode_rounds(source,projection):
    try:
        yield row_bytes(HEADER)
        async for report in source:
            for row in projection.rows(report):yield row_bytes(row)
    finally:await source.aclose()
