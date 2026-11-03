"""Registry of bank adapters. To add a bank: write a module with CODE, NAME,
SOURCE_URL, fetch(session) -> str|bytes and parse(raw) -> (list[Rate], as_of|None),
then add it to ADAPTERS below and a fixture + test in tests/.

VietinBank (vietin.py) is kept but switched off: since 01/11/2026 its website
refuses GitHub's servers (HTTP 405), and its rates matched Vietcombank and BIDV
at every term anyway. Add `vietin` back to ADAPTERS to try it again.
"""
from . import acb, agri, bidv, ocb, stb, tpb, vcb, vietin  # noqa: F401

ADAPTERS = [vcb, bidv, agri, acb, tpb, stb, ocb]
