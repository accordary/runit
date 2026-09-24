"""Feature extraction and interpretable diagnosis for runit services."""
import re
from collections import namedtuple

from .edge_model import load_model

PERM_RE = re.compile(r"permission denied|eacces|not permitted|operation not permitted", re.I)
DISK_RE = re.compile(r"no space left|enospc|disk full|write error", re.I)
DEP_RE = re.compile(r"connection refused|waiting for|timed out|unreachable|no such host|econnrefused", re.I)
ERR_RE = re.compile(r"\b(error|fatal|fail(ed|ure)?|panic)\b", re.I)

REMEDY = {
    "healthy": "No action: signals are within normal bounds.",
    "respawn_loop": "Service restarts faster than it stabilises; inspect ./run exit path and add a backoff in ./finish.",
    "dependency_stall": "Service is blocked on an unavailable peer; check the dependency's own supervision and network reachability.",
    "permission_fault": "Service cannot access a required path; check ownership/mode of the service directory and its data paths.",
    "disk_pressure": "Writes are failing for lack of space; free space on the filesystem backing the log and data directories.",
}

Diagnosis = namedtuple(
    "Diagnosis",
    "label confidence probabilities features contributions evidence remedy model_version load_stages",
)


def extract_features(exit_code, restarts, uptime_seconds, log_lines, window_seconds=60.0):
    """Map raw supervision signals to the model's feature vector, with evidence."""
    lines = list(log_lines or [])
    n = max(len(lines), 1)
    window = max(float(window_seconds), 1.0)
    evidence = {"permission": [], "disk": [], "dependency": [], "error": []}
    perm = disk = dep = err = 0
    for line in lines:
        if PERM_RE.search(line):
            perm += 1
            evidence["permission"].append(line.strip())
        if DISK_RE.search(line):
            disk += 1
            evidence["disk"].append(line.strip())
        if DEP_RE.search(line):
            dep += 1
            evidence["dependency"].append(line.strip())
        if ERR_RE.search(line):
            err += 1
            evidence["error"].append(line.strip())
    vector = [
        1.0 if exit_code not in (0, None) else 0.0,
        min(float(restarts) / window * 60.0, 10.0) / 10.0,
        err / float(n),
        perm / float(n),
        disk / float(n),
        dep / float(n),
        1.0 if uptime_seconds is not None and uptime_seconds < 5.0 else 0.0,
    ]
    for key in evidence:
        evidence[key] = evidence[key][:5]
    return vector, evidence


def diagnose_service(exit_code, restarts, uptime_seconds, log_lines, window_seconds=60.0, model=None):
    model = model or load_model()
    vector, evidence = extract_features(exit_code, restarts, uptime_seconds, log_lines, window_seconds)
    probs = model.score(vector)
    label = max(probs, key=probs.get)
    weights = model.weights[label]
    contributions = sorted(
        ((model.features[i], weights[i] * vector[i]) for i in range(len(vector))),
        key=lambda pair: abs(pair[1]),
        reverse=True,
    )
    return Diagnosis(
        label=label,
        confidence=probs[label],
        probabilities=probs,
        features=dict(zip(model.features, vector)),
        contributions=contributions,
        evidence=evidence,
        remedy=REMEDY[label],
        model_version=model.version,
        load_stages=model.load_stages,
    )
