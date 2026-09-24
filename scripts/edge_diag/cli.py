"""Command line entry point: python3 -m scripts.edge_diag.cli --help"""
import argparse
import json
import sys

from .diagnose import diagnose_service
from .edge_model import ModelLoadError, load_model


def main(argv=None):
    parser = argparse.ArgumentParser(description="runit embedded AI diagnostics (local edge model, no cloud API)")
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--restarts", type=float, default=0.0)
    parser.add_argument("--uptime", type=float, default=3600.0)
    parser.add_argument("--window", type=float, default=60.0)
    parser.add_argument("--log", default="-", help="log file to read, '-' for stdin, '' for none")
    parser.add_argument("--model", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.log == "-":
        lines = sys.stdin.read().splitlines() if not sys.stdin.isatty() else []
    elif args.log:
        with open(args.log, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
    else:
        lines = []

    try:
        model = load_model(args.model)
    except ModelLoadError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2

    d = diagnose_service(args.exit_code, args.restarts, args.uptime, lines, args.window, model=model)
    if args.json:
        print(json.dumps({
            "label": d.label, "confidence": round(d.confidence, 4),
            "probabilities": {k: round(v, 4) for k, v in d.probabilities.items()},
            "top_contributions": [[k, round(v, 4)] for k, v in d.contributions[:3]],
            "evidence": d.evidence, "remedy": d.remedy,
            "model_version": d.model_version, "load_stages": list(d.load_stages),
        }, indent=2))
    else:
        print("diagnosis : %s (confidence %.2f, model %s)" % (d.label, d.confidence, d.model_version))
        print("why       : " + ", ".join("%s=%+.2f" % (k, v) for k, v in d.contributions[:3]))
        for kind, items in d.evidence.items():
            for line in items:
                print("evidence  : [%s] %s" % (kind, line))
        print("remedy    : %s" % d.remedy)
    return 0 if d.label == "healthy" else 1


if __name__ == "__main__":
    sys.exit(main())
