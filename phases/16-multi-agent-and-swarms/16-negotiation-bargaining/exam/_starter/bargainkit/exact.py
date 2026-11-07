"""Complete exact Decimal/Fraction atoms, arithmetic, grid-value and optional scalar codecs."""
from decimal import Decimal
from fractions import Fraction
def decimal_exact(value):
    value=Fraction(value);sign=int(value<0);n=abs(value.numerator);d=value.denominator;a=b=0
    while d%2==0:a+=1;d//=2
    while d%5==0:b+=1;d//=5
    if d!=1:raise ValueError('finite decimal required')
    scale=max(a,b);n*=2**(scale-a)*5**(scale-b)
    return Decimal((sign,tuple(map(int,str(n))),-scale))
def add(left,right):return decimal_exact(Fraction(left)+Fraction(right))
def subtract(left,right):return decimal_exact(Fraction(left)-Fraction(right))
def multiply(left,right):return decimal_exact(Fraction(left)*Fraction(right))
def amount_atoms(price,tick):
    if not price.is_finite()or price<0 or not tick.is_finite()or tick<=0:raise ValueError('finite nonnegative price and positive tick required')
    p=Fraction(price);t=Fraction(tick);return p.numerator*t.denominator,t.numerator*p.denominator
def price_field(value):return None if value is None else str(value)
def price_value(value):return None if value is None else Decimal(value)
def tick_price(units,tick):
    sign,digits,exponent=tick.as_tuple();coefficient=int(''.join(map(str,digits)))*units
    return Decimal((int(coefficient<0),tuple(map(int,str(abs(coefficient)))),exponent))
