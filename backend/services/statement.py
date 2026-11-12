"""Read a bank or M-Pesa statement exported as CSV. Standard library only, no Flask."""
import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_CHARS = 400000
MAX_ROWS = 2000
HEADS = (
    ('amount', ('credit', 'paid in', 'money in', 'amount')),
    ('reference', ('receipt', 'reference', 'ref', 'transaction id', 'trans id', 'txn', 'transaction no')),
    ('date', ('date', 'time')),
    ('details', ('detail', 'narr', 'description', 'particular', 'name', 'account', 'remark')),
)
DATE_TOKEN = re.compile(r'\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}[ -][A-Za-z]{3}[ -]\d{2,4}')
DATE_FORMATS = ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y',
                '%d-%b-%Y', '%d %b %Y', '%d-%b-%y', '%d %b %y')
CENT = Decimal('0.01')


class StatementError(ValueError):
    pass


def to_amount(text):
    """A positive amount with 2 decimals, or None (blank, zero, negative, not a number)."""
    value = str(text or '').strip()
    if not value or value.startswith('(') or value.startswith('-'):
        return None
    value = re.sub(r'(?i)\b(kes|kshs?|ksh\.?)\b', '', value)
    value = value.replace(',', '').replace(' ', '')
    try:
        amount = Decimal(value)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0 or amount > Decimal('9999999999.99'):
        return None
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)


def parse_date(text):
    match = DATE_TOKEN.search(str(text or ''))
    if not match:
        return None
    token = match.group(0)
    for fmt in DATE_FORMATS:
        try:
            found = datetime.strptime(token, fmt).date()
        except ValueError:
            continue
        return found if found <= date.today() else None
    return None


def _detect(header):
    lowered = [cell.strip().lower() for cell in header]
    found, used = {}, set()
    for key, tokens in HEADS:
        for token in tokens:
            hit = next((i for i, cell in enumerate(lowered) if i not in used and token in cell), None)
            if hit is not None:
                found[key] = hit
                used.add(hit)
                break
    return found


def _rows(text):
    first = text.splitlines()[0] if text.splitlines() else ''
    delimiter = max((',', ';', '\t'), key=first.count)
    return list(csv.reader(io.StringIO(text), delimiter=delimiter))


def parse(text):
    """Return (rows, skipped). Each row: date, reference, amount, details."""
    if len(text) > MAX_CHARS:
        raise StatementError('That file is too large. Export a shorter period.')
    table = _rows(text)
    start, columns = None, {}
    for index, row in enumerate(table[:15]):
        columns = _detect(row)
        if 'amount' in columns:
            start = index
            break
    if start is None:
        raise StatementError('Could not find an amount column. The first row needs headings such as '
                             'Date, Reference, Details and Credit (or Amount).')
    out, skipped = [], 0
    for row in table[start + 1:start + 1 + MAX_ROWS]:
        if not any(cell.strip() for cell in row):
            continue

        def cell(key):
            index = columns.get(key)
            return row[index].strip() if index is not None and index < len(row) else ''
        amount = to_amount(cell('amount'))
        if amount is None:
            skipped += 1
            continue
        details = cell('details')[:200]
        when = parse_date(cell('date'))
        reference = re.sub(r'\s+', '', cell('reference')).upper()[:24]
        if not reference:
            seed = '%s|%s|%s' % (cell('date'), amount, details)
            reference = 'H' + hashlib.sha1(seed.encode('utf8')).hexdigest()[:12].upper()
        out.append({'date': when, 'reference': reference, 'amount': amount, 'details': details})
    return out, skipped
