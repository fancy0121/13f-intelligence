"""Outcome adapter framework (EXPERIMENTAL, v0.2).

Design goal: compute forward outcomes from an approved market-data provider
starting at information_available_date. Currently NO provider passes the
acceptance gate (symbol identity), so evaluation is NOT_EVALUATED - but the
framework, tests and future-ready hooks are delivered.
"""

