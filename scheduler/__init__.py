"""Scheduler package for AI-assisted café rostering (Milestone 1).

Modules:
- config: load and validate configuration (JSON or YAML if available)
- data_io: CSV IO helpers and timezone utilities
- constraints: hard constraint predicates
- scoring: role scoring and fairness penalties
- engine_baseline: greedy assignment engine with light backtracking
- validator: post-generation validations
- feedback: stubs for future learning from manager feedback
- cli: command-line interface entrypoints
"""

__all__ = [
    "config",
    "data_io",
    "constraints",
    "scoring",
    "engine_baseline",
    "validator",
    "feedback",
    "cli",
]


