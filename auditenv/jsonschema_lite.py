"""A small, dependency-free JSON Schema validator for the subset used in schemas/.

Supported keywords: type (incl. type lists), enum, const, properties, required,
additionalProperties (bool or schema), items, minItems, maxItems, minLength, maxLength,
pattern (re.search, our patterns are anchored), minimum, maximum, oneOf, $ref (local
"#/$defs/..." and sibling files like "findings.schema.json"), $defs. Annotation keywords
($schema, $id, title, description) are ignored. Any OTHER keyword raises at load time, so a
schema can never silently use something this validator does not check.

Deliberate strictness: "integer" accepts only real ints (not bool, not 5.0); "number" accepts
int/float but not bool. Money is never a float in this project.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass

KNOWN = {"$schema", "$id", "title", "description", "$defs", "type", "enum", "const", "properties", "required",
         "additionalProperties", "items", "minItems", "maxItems", "minLength", "maxLength", "pattern", "minimum",
         "maximum", "oneOf", "$ref"}


@dataclass
class ValidationError:
    path: tuple
    validator: str
    message: str

    @property
    def absolute_path(self):  # same attribute name as the jsonschema package, for readability
        return list(self.path)


def _type_ok(value, t: str) -> bool:
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "integer":
        return type(value) is int
    if t == "number":
        return type(value) in (int, float)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    raise ValueError(f"unknown type {t!r}")


def _check_keywords(schema, where="#"):
    if isinstance(schema, bool):
        return
    unknown = set(schema) - KNOWN
    if unknown:
        raise ValueError(f"unsupported schema keywords at {where}: {sorted(unknown)}")
    for k, sub in schema.get("properties", {}).items():
        _check_keywords(sub, f"{where}/properties/{k}")
    for k, sub in schema.get("$defs", {}).items():
        _check_keywords(sub, f"{where}/$defs/{k}")
    for k in ("items", "additionalProperties"):
        if isinstance(schema.get(k), dict):
            _check_keywords(schema[k], f"{where}/{k}")
    for n, sub in enumerate(schema.get("oneOf", [])):
        _check_keywords(sub, f"{where}/oneOf/{n}")


class Validator:
    def __init__(self, schema: dict, registry: dict | None = None):
        """registry: {"$id": schema} for cross-file $ref."""
        self.schema = schema
        self.registry = dict(registry or {})
        if "$id" in schema:
            self.registry.setdefault(schema["$id"], schema)
        for s in self.registry.values():
            _check_keywords(s)
        _check_keywords(schema)

    # ------------------------------------------------------------------ refs
    def _resolve(self, ref: str, root: dict):
        doc_part, _, frag = ref.partition("#")
        if doc_part:
            base = posixpath.dirname(root.get("$id", ""))
            key = posixpath.normpath(posixpath.join(base, doc_part)) if base else doc_part
            if key not in self.registry:
                raise ValueError(f"unresolvable $ref {ref!r}")
            root = self.registry[key]
        node = root
        for part in [p for p in frag.split("/") if p]:
            node = node[part]
        return node, root

    # -------------------------------------------------------------- validate
    def iter_errors(self, value):
        yield from self._errors(value, self.schema, self.schema, ())

    def is_valid(self, value) -> bool:
        return next(self.iter_errors(value), None) is None

    def _errors(self, v, s, root, path):
        if s is True:
            return
        if s is False:
            yield ValidationError(path, "false", "no value is allowed here")
            return
        if "$ref" in s:
            target, troot = self._resolve(s["$ref"], root)
            yield from self._errors(v, target, troot, path)
        if "type" in s:
            types = s["type"] if isinstance(s["type"], list) else [s["type"]]
            if not any(_type_ok(v, t) for t in types):
                yield ValidationError(path, "type", f"{v!r:.60} is not of type {types}")
                return
        if "enum" in s and not any(v == e and type(v) is type(e) for e in s["enum"]):
            yield ValidationError(path, "enum", f"{v!r:.60} is not one of {s['enum']}")
        if "const" in s and not (v == s["const"] and type(v) is type(s["const"])):
            yield ValidationError(path, "const", f"{v!r:.60} is not {s['const']!r}")
        if isinstance(v, str):
            if "minLength" in s and len(v) < s["minLength"]:
                yield ValidationError(path, "minLength", "string too short")
            if "maxLength" in s and len(v) > s["maxLength"]:
                yield ValidationError(path, "maxLength", "string too long")
            if "pattern" in s and not re.search(s["pattern"], v):
                yield ValidationError(path, "pattern", f"{v!r:.60} does not match {s['pattern']!r}")
        if type(v) in (int, float):
            if "minimum" in s and v < s["minimum"]:
                yield ValidationError(path, "minimum", f"{v} < {s['minimum']}")
            if "maximum" in s and v > s["maximum"]:
                yield ValidationError(path, "maximum", f"{v} > {s['maximum']}")
        if isinstance(v, list):
            if "minItems" in s and len(v) < s["minItems"]:
                yield ValidationError(path, "minItems", "too few items")
            if "maxItems" in s and len(v) > s["maxItems"]:
                yield ValidationError(path, "maxItems", "too many items")
            if "items" in s:
                for i, item in enumerate(v):
                    yield from self._errors(item, s["items"], root, path + (i,))
        if isinstance(v, dict):
            for k in s.get("required", []):
                if k not in v:
                    yield ValidationError(path, "required", f"{k!r} is a required property")
            props = s.get("properties", {})
            for k, item in v.items():
                if k in props:
                    yield from self._errors(item, props[k], root, path + (k,))
                elif "additionalProperties" in s:
                    ap = s["additionalProperties"]
                    if ap is False:
                        yield ValidationError(path + (k,), "additionalProperties",
                                              f"additional property {k!r} is not allowed")
                    elif isinstance(ap, dict):
                        yield from self._errors(item, ap, root, path + (k,))
        if "oneOf" in s:
            ok = sum(1 for sub in s["oneOf"] if next(self._errors(v, sub, root, path), None) is None)
            if ok != 1:
                yield ValidationError(path, "oneOf", f"matches {ok} of the oneOf alternatives, expected exactly 1")


def validate(value, schema: dict, registry: dict | None = None) -> None:
    err = next(Validator(schema, registry).iter_errors(value), None)
    if err is not None:
        where = "/".join(str(p) for p in err.path) or "<root>"
        raise ValueError(f"{where}: {err.message}")
