# Archive

[English](README.md) | [中文](README.zh-CN.md)

## Purpose

This directory holds superseded, exploratory, or legacy Markdown documents that should remain available for history but no longer act as active docs.

## Current Contents

- `planning_acceptance_record_2026-04-09.*`: dated acceptance sample
- `planning_acceptance_record_2026-04-12.*`: dated semi-real acceptance refresh after the acceptance helper expansion
- `planning_acceptance_handoff.*`: historical handoff snapshot
- `planning_acceptance_commit_plan.*`: old commit split guidance
- `cleanup_commit_plan.*`: one-off cleanup split plan
- `local_install_validation_2026-04-09.*`: dated local install validation note

## Read This Directory When

- you need historical acceptance evidence
- you want to understand an older cleanup or handoff decision
- you are checking a dated local validation note rather than the current install guide

## Planning Evidence Promotion Policy

Promote a planning dry-run into a dated archive record when:

- the full dry-run bundle is green
- the run was not label-filtered
- the current change affects planning/runtime contracts, release-facing acceptance coverage, or the planning evidence workflow

Use `python3 scripts/runtime/run_planning_acceptance_bundle.py --json --date YYYY-MM-DD` for that promotion step. Existing dated archive records are preserved.
