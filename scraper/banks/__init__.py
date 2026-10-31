"""Registry of bank adapters. To add a bank: write a module with CODE, NAME,
SOURCE_URL, fetch(session) -> str and parse(raw) -> (list[Rate], as_of|None),
then add it to ADAPTERS below and a fixture + test in tests/."""
from . import acb, agri, bidv, tpb, vcb, vietin

ADAPTERS = [vcb, bidv, vietin, agri, acb, tpb]
