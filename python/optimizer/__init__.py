"""Optimizer package for computing Pareto front on uncovered spaces.

Modules:
- data: loaders for uncovered block areas.
- options: parse options.csv and filter ground options.
- model: compute per-block option metrics (cost, CO2).
- ortools_solver: budget-constrained frontier using OR-Tools CP-SAT.
- cli: command-line entry point.
"""
