from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import load_config
from .data_io import read_employees, read_shifts, write_assignments
from .engine_baseline import greedy_schedule, build_requirements_for_day
from .validator import summarize_assignments, validate_assignments


def _cmd_generate(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    employees = read_employees(args.employees)
    shifts = read_shifts(args.shifts, week_id=args.week)
    if shifts.empty:
        raise SystemExit(f"No shifts found for week {args.week}")
    assignments = greedy_schedule(employees, shifts, cfg)

    # Build requirements by date for validation summary
    req_by_date = {}
    for date in sorted(shifts["date"].unique()):
        date_str = pd.Timestamp(date).strftime("%Y-%m-%d")
        req_by_date[date_str] = build_requirements_for_day(date_str, cfg)

    validate_assignments(
        employees,
        shifts,
        assignments,
        start_hm=cfg.default_shift.start,
        end_hm=cfg.default_shift.end,
        requirements_by_date=req_by_date,
    )
    write_assignments(args.out, assignments)
    print("Assignments written to", args.out)
    print(summarize_assignments(assignments))


def _cmd_validate(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    employees = read_employees(args.employees)
    shifts = read_shifts(args.shifts)
    assignments = pd.read_csv(args.assignments)
    validate_assignments(
        employees,
        shifts,
        assignments,
        start_hm=cfg.default_shift.start,
        end_hm=cfg.default_shift.end,
    )
    print("Validation passed.")


def _cmd_summarize(args: argparse.Namespace) -> None:
    assignments = pd.read_csv(args.assignments)
    print(summarize_assignments(assignments))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scheduler")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="Generate assignments for a week")
    g.add_argument("--week", required=True)
    g.add_argument("--employees", required=True)
    g.add_argument("--shifts", required=True)
    g.add_argument("--config", required=True)
    g.add_argument("--out", required=True)
    g.set_defaults(func=_cmd_generate)

    v = sub.add_parser("validate", help="Validate an assignments CSV")
    v.add_argument("--employees", required=True)
    v.add_argument("--shifts", required=True)
    v.add_argument("--assignments", required=True)
    v.add_argument("--config", required=True)
    v.set_defaults(func=_cmd_validate)

    s = sub.add_parser("summarize", help="Summarize an assignments CSV")
    s.add_argument("--assignments", required=True)
    s.set_defaults(func=_cmd_summarize)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()


