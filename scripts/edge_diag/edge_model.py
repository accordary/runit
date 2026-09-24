"""Serial loader for the bundled local edge model.

The loader performs the documented stages in strict order and never opens a
network socket: the model is a plain JSON artefact shipped in this directory.
"""
import json
import math
import os
import threading

MODEL_FILENAME = "model.json"
MAX_MODEL_BYTES = 1 << 20  # 1 MiB ceiling; the shipped artefact is ~1 KiB.

LOAD_STAGES = (
    "locate",     # resolve the artefact path
    "stat",       # size/permission check before any read
    "read",       # single sequential read into memory
    "parse",      # JSON decode
    "validate",   # schema and shape checks
    "ready",      # publish the immutable model object
)

_LOAD_LOCK = threading.Lock()
_CACHE = {}


class ModelLoadError(RuntimeError):
    """Raised when a load stage fails; carries the stage for interpretability."""

    def __init__(self, stage, detail):
        self.stage = stage
        self.detail = detail
        super().__init__("edge model load failed at stage '%s': %s" % (stage, detail))


class EdgeModel:
    def __init__(self, spec, path, stages):
        self.name = spec["name"]
        self.version = spec["version"]
        self.classes = tuple(spec["classes"])
        self.features = tuple(spec["features"])
        self.weights = {k: tuple(float(x) for x in v) for k, v in spec["weights"].items()}
        self.bias = {k: float(v) for k, v in spec["bias"].items()}
        self.path = path
        self.load_stages = tuple(stages)

    def score(self, vector):
        if len(vector) != len(self.features):
            raise ValueError("expected %d features, got %d" % (len(self.features), len(vector)))
        raw = {}
        for cls in self.classes:
            w = self.weights[cls]
            raw[cls] = self.bias[cls] + sum(w[i] * float(vector[i]) for i in range(len(w)))
        top = max(raw.values())
        exp = {c: math.exp(v - top) for c, v in raw.items()}
        total = sum(exp.values())
        return {c: v / total for c, v in exp.items()}


def _default_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILENAME)


def load_model(path=None, use_cache=True):
    """Load the edge model serially. Concurrent callers queue on a single lock."""
    path = path or _default_path()
    stages = []
    with _LOAD_LOCK:
        if use_cache and path in _CACHE:
            return _CACHE[path]

        stages.append("locate")
        if not os.path.exists(path):
            raise ModelLoadError("locate", "no model artefact at %s" % path)

        stages.append("stat")
        try:
            size = os.stat(path).st_size
        except OSError as exc:
            raise ModelLoadError("stat", str(exc))
        if size == 0:
            raise ModelLoadError("stat", "model artefact is empty")
        if size > MAX_MODEL_BYTES:
            raise ModelLoadError("stat", "model artefact exceeds %d bytes" % MAX_MODEL_BYTES)

        stages.append("read")
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = handle.read()
        except OSError as exc:
            raise ModelLoadError("read", str(exc))

        stages.append("parse")
        try:
            spec = json.loads(payload)
        except ValueError as exc:
            raise ModelLoadError("parse", str(exc))

        stages.append("validate")
        for key in ("name", "version", "classes", "features", "weights", "bias"):
            if key not in spec:
                raise ModelLoadError("validate", "missing key '%s'" % key)
        n = len(spec["features"])
        for cls in spec["classes"]:
            if cls not in spec["weights"] or cls not in spec["bias"]:
                raise ModelLoadError("validate", "class '%s' has no weights/bias" % cls)
            if len(spec["weights"][cls]) != n:
                raise ModelLoadError("validate", "class '%s' weight length != %d" % (cls, n))

        stages.append("ready")
        model = EdgeModel(spec, path, stages)
        if use_cache:
            _CACHE[path] = model
        return model
