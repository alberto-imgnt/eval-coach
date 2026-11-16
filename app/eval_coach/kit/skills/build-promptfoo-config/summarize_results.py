"""Summarize a promptfoo results.json into per-criterion PASS/FAIL/NOT CHECKED and pass rates.

Usage: python summarize_results.py results.json [test-name-prefix]

A criterion (the assertion's `metric`) passes for a test only if every assertion carrying that metric passed.
An assertion whose reason starts with "NOT CHECKED" marks the criterion as not checked.
With a prefix (for example `run-`), only tests whose name starts with it are summarized.
"""
import json
import sys


def main(path, prefix=""):
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)["results"]["results"]

    metrics = []
    tests = []
    for row in sorted(rows, key=lambda r: r.get("testIdx", 0)):
        name = (row.get("testCase") or {}).get("description") or f"test-{row.get('testIdx', '?')}"
        if not name.startswith(prefix):
            continue
        verdicts = {}
        for comp in (row.get("gradingResult") or {}).get("componentResults", []):
            metric = (comp.get("assertion") or {}).get("metric") or "(no metric)"
            if metric not in metrics:
                metrics.append(metric)
            if str(comp.get("reason", "")).startswith("NOT CHECKED"):
                verdicts[metric] = "NOT CHECKED"
            elif verdicts.get(metric) != "NOT CHECKED":
                verdicts[metric] = "FAIL" if verdicts.get(metric) == "FAIL" or not comp.get("pass") else "PASS"
        tests.append((name, verdicts))

    for name, verdicts in tests:
        counts = {s: sum(1 for m in metrics if verdicts.get(m) == s) for s in ("PASS", "FAIL", "NOT CHECKED")}
        print(f"== {name}")
        for metric in metrics:
            print(f"{metric} {verdicts.get(metric, 'FAIL')}")
        print(f"-> {counts['PASS']} passed, {counts['FAIL']} failed, {counts['NOT CHECKED']} NOT CHECKED\n")

    if len(tests) > 1:
        print("== Pass rate per criterion")
        for metric in metrics:
            if any(v.get(metric) == "NOT CHECKED" for _, v in tests):
                print(f"{metric}: NOT CHECKED")
            else:
                ok = sum(1 for _, v in tests if v.get(metric) == "PASS")
                print(f"{metric}: {ok}/{len(tests)}")


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("Usage: python summarize_results.py results.json [test-name-prefix]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else "")
