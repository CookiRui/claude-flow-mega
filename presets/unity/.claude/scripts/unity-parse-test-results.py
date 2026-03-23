#!/usr/bin/env python3
"""Parse Unity test results (NUnit 3 XML or log fallback).

Usage:
    python unity-parse-test-results.py <xml-file>             # XML mode
    python unity-parse-test-results.py --from-log <log-file>  # Log fallback

Output: JSON to stdout.

Fields:
    source   — "xml", "log", or "error"
    result   — "passed", "failed", or "error"
    total    — total test count
    passed   — passed test count
    failed   — failed test count
    skipped  — skipped test count
    duration — total duration in seconds (float)
    failures — array of {name, message, stackTrace}

Python stdlib only — no external dependencies.
"""

import json
import sys
import xml.etree.ElementTree as ET


def parse_xml(path):
    """Parse NUnit 3 XML result file."""
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        return {"source": "error", "result": "error", "total": 0, "passed": 0,
                "failed": 0, "skipped": 0, "duration": 0.0,
                "failures": [], "error": f"XML parse error: {e}"}
    except FileNotFoundError:
        return {"source": "error", "result": "error", "total": 0, "passed": 0,
                "failed": 0, "skipped": 0, "duration": 0.0,
                "failures": [], "error": "XML file not found"}

    root = tree.getroot()

    total = int(root.get("testcasecount", "0"))
    passed = int(root.get("passed", "0"))
    failed = int(root.get("failed", "0"))
    skipped = int(root.get("skipped", "0"))
    result = root.get("result", "Unknown").lower()
    duration = float(root.get("duration", "0"))

    # Map NUnit result to simplified result
    if result == "passed":
        simple_result = "passed"
    elif result in ("failed", "error"):
        simple_result = "failed"
    else:
        simple_result = "error"

    failures = []
    for tc in root.iter("test-case"):
        if tc.get("result") == "Failed":
            name = tc.get("fullname", tc.get("name", "unknown"))
            msg_el = tc.find(".//message")
            st_el = tc.find(".//stack-trace")
            failures.append({
                "name": name,
                "message": msg_el.text.strip() if msg_el is not None and msg_el.text else "",
                "stackTrace": st_el.text.strip() if st_el is not None and st_el.text else "",
            })

    return {
        "source": "xml",
        "result": simple_result,
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration": duration,
        "failures": failures,
    }


def parse_log(path):
    """Fallback: scan Unity log for test result markers."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return {"source": "error", "result": "error", "total": 0, "passed": 0,
                "failed": 0, "skipped": 0, "duration": 0.0,
                "failures": [], "error": "Log file not found"}

    finished_count = 0
    run_finished = False
    compile_errors = []

    for line in lines:
        stripped = line.strip()
        if "CallbacksDelegator: TestFinished" in stripped:
            finished_count += 1
        if "CallbacksDelegator: RunFinished" in stripped:
            run_finished = True
        # Detect compile errors (CSxxxx)
        if ": error CS" in stripped:
            compile_errors.append(stripped)

    if compile_errors:
        return {
            "source": "log",
            "result": "error",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0.0,
            "failures": [{"name": "CompileError", "message": e, "stackTrace": ""}
                         for e in compile_errors[:10]],
        }

    return {
        "source": "log",
        "result": "passed" if run_finished else "error",
        "total": finished_count,
        "passed": finished_count if run_finished else 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0.0,
        "failures": [] if run_finished else [
            {"name": "Incomplete", "message": "RunFinished not found in log", "stackTrace": ""}
        ],
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"source": "error", "result": "error", "error": "No input file specified"}))
        sys.exit(1)

    if sys.argv[1] == "--from-log":
        if len(sys.argv) < 3:
            print(json.dumps({"source": "error", "result": "error", "error": "No log file specified"}))
            sys.exit(1)
        result = parse_log(sys.argv[2])
    else:
        result = parse_xml(sys.argv[1])

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
