"""Complete exact scalar codecs, typed family validation and atomic JSON snapshot I/O."""
from pathlib import Path
from fractions import Fraction
from decimal import Decimal
import json,os
from .support import validate_config
def probability_fields(value):return [str(value.numerator),str(value.denominator)]
def probability_value(fields):return Fraction(int(fields[0]),int(fields[1]))
def decimal_field(value):return str(value)
def decimal_value(value):return Decimal(value)
class SnapshotDriver:
    def __init__(self,path):self.path=Path(path);self.closed=False
    def save(self,document):
        if self.closed:raise ValueError('closed snapshot driver')
        self.path.parent.mkdir(parents=True,exist_ok=True);temporary=self.path.with_name(self.path.name+'.pending')
        with temporary.open('w',encoding='utf-8')as handle:json.dump(document,handle,ensure_ascii=False,allow_nan=False,separators=(',',':'))
        os.replace(temporary,self.path)
    def load(self):
        if self.closed:raise ValueError('closed snapshot driver')
        with self.path.open(encoding='utf-8')as handle:return json.load(handle)
    def close(self):self.closed=True
