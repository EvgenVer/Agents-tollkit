import csv
from io import StringIO


def read_rows(text):
    return list(csv.DictReader(StringIO(text)))
