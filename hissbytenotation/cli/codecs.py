"""Codec helpers for the phase 1 CLI."""

from __future__ import annotations

import json
import pprint
import re
import shlex
import xml.etree.ElementTree as element_tree
from pathlib import Path
from typing import Any

from hissbytenotation import dumps as hbn_dumps
from hissbytenotation import loads as hbn_loads
from hissbytenotation.dump_to_json import CustomEncoder

from .errors import (
    InputParseError,
    OperationTypeError,
    StrictConversionError,
    UnsupportedFormatError,
)

tomllib: Any = None
try:
    import tomllib  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - exercised on older Python only
    try:
        import tomli as tomllib  # type: ignore[no-redef, import-not-found]
    except ImportError:  # pragma: no cover - exercised on older Python only
        tomllib = None


INPUT_FORMATS = {"hbn", "json", "toml", "xml", "bmn"}
OUTPUT_FORMATS = {"hbn", "json", "xml", "bmn"}


def normalize_format_name(format_name: str | None, *, output: bool = False) -> str:
    """Normalize and validate a format name."""
    if format_name is None:
        return "hbn"
    normalized = format_name.lower()
    allowed = OUTPUT_FORMATS if output else INPUT_FORMATS
    if normalized not in allowed:
        direction = "output" if output else "input"
        raise UnsupportedFormatError(f"Unsupported {direction} format: {format_name}")
    return normalized


def infer_format_from_path(path: str | Path | None, *, output: bool = False) -> str:
    """Infer a format from a file extension, defaulting to HBN."""
    if path is None:
        return "hbn"
    suffix = Path(path).suffix.lower()
    suffix_map = {
        ".hbn": "hbn",
        ".py": "hbn",
        ".json": "json",
        ".toml": "toml",
        ".xml": "xml",
        ".bmn": "bmn",
        ".bash": "bmn",
    }
    inferred = suffix_map.get(suffix, "hbn")
    return normalize_format_name(inferred, output=output)


def parse_value(source_text: str, input_format: str, *, strict: bool = False) -> Any:
    """Parse a value from a supported input format."""
    normalized = normalize_format_name(input_format)
    if normalized == "hbn":
        try:
            return hbn_loads(source_text)
        except (SyntaxError, ValueError) as exc:
            raise InputParseError(f"Could not parse HBN input: {exc}") from exc
    if normalized == "json":
        try:
            return json.loads(source_text)
        except json.JSONDecodeError as exc:
            raise InputParseError(f"Could not parse JSON input: {exc}") from exc
    if normalized == "toml":
        if tomllib is None:
            raise UnsupportedFormatError("TOML input requires Python 3.11+ or the optional tomli package.")
        try:
            return tomllib.loads(source_text)
        except Exception as exc:  # tomllib exception type differs by implementation
            raise InputParseError(f"Could not parse TOML input: {exc}") from exc
    if normalized == "xml":
        return xml_to_value(source_text, strict=strict)
    if normalized == "bmn":
        return parse_bmn(source_text)
    raise UnsupportedFormatError(f"Unsupported input format: {input_format}")


def render_value(
    value: Any,
    output_format: str,
    *,
    pretty: bool = False,
    compact: bool = False,
    sort_keys: bool = False,
    indent: int | None = None,
    strict: bool = False,
) -> str:
    """Serialize a value to a supported output format."""
    normalized = normalize_format_name(output_format, output=True)
    if normalized == "hbn":
        return dump_hbn(value, pretty=pretty, compact=compact, sort_keys=sort_keys, indent=indent)
    if normalized == "json":
        return dump_json(value, pretty=pretty, compact=compact, sort_keys=sort_keys, indent=indent, strict=strict)
    if normalized == "xml":
        return dump_xml(value)
    if normalized == "bmn":
        return dump_bmn(value)
    raise UnsupportedFormatError(f"Unsupported output format: {output_format}")


def dump_hbn(
    value: Any,
    *,
    pretty: bool = False,
    compact: bool = False,
    sort_keys: bool = False,
    indent: int | None = None,
) -> str:
    """Serialize a value as HBN."""
    if compact:
        return hbn_dumps(value)
    if pretty or sort_keys or indent is not None:
        pretty_indent = 4 if indent is None else max(indent, 1)
        return pprint.pformat(value, indent=pretty_indent, sort_dicts=sort_keys, width=88)
    return hbn_dumps(value)


def dump_json(
    value: Any,
    *,
    pretty: bool = False,
    compact: bool = False,
    sort_keys: bool = False,
    indent: int | None = None,
    strict: bool = False,
) -> str:
    """Serialize a value as JSON."""
    if strict:
        ensure_json_safe(value)
    json_indent = None
    separators = None
    if compact:
        separators = (",", ":")
    elif pretty or indent is not None:
        json_indent = 2 if indent is None else indent
    return json.dumps(value, cls=CustomEncoder, indent=json_indent, sort_keys=sort_keys, separators=separators)


def ensure_json_safe(value: Any) -> None:
    """Refuse conversions that lose information in strict mode."""
    if isinstance(value, bytes):
        raise StrictConversionError("Strict mode refuses to convert bytes to JSON strings.")
    if isinstance(value, tuple):
        raise StrictConversionError("Strict mode refuses to convert tuples to JSON arrays.")
    if isinstance(value, set):
        raise StrictConversionError("Strict mode refuses to convert sets to JSON arrays.")
    if value is Ellipsis:
        raise StrictConversionError("Strict mode refuses to convert Ellipsis to JSON.")
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise StrictConversionError("Strict mode refuses to convert non-string dict keys to JSON.")
        for nested_value in value.values():
            ensure_json_safe(nested_value)
        return
    if isinstance(value, (list, tuple, set)):
        for nested_value in value:
            ensure_json_safe(nested_value)


def xml_to_value(source_text: str, *, strict: bool = False) -> Any:
    """Parse XML into the documented mapping."""
    try:
        root = element_tree.fromstring(source_text)
    except element_tree.ParseError as exc:
        raise InputParseError(f"Could not parse XML input: {exc}") from exc
    return {root.tag: _xml_element_to_value(root, strict=strict)}


def _xml_element_to_value(element: element_tree.Element, *, strict: bool = False) -> Any:
    children = list(element)
    text = (element.text or "").strip()
    if not children and not element.attrib:
        return text

    node: dict[str, Any] = {}
    if element.attrib:
        node["@attrs"] = dict(element.attrib)

    grouped_children: dict[str, list[Any]] = {}
    for child in children:
        tail = (child.tail or "").strip()
        if tail:
            if strict:
                raise StrictConversionError("Strict mode refuses XML with mixed content.")
            grouped_children.setdefault("#tail", []).append(tail)
        grouped_children.setdefault(child.tag, []).append(_xml_element_to_value(child, strict=strict))

    for child_tag, child_values in grouped_children.items():
        if child_tag == "#tail":
            node["#tail"] = child_values
            continue
        node[child_tag] = child_values[0] if len(child_values) == 1 else child_values

    if text:
        if children and strict:
            raise StrictConversionError("Strict mode refuses XML elements that combine text and child nodes.")
        node["#text"] = text

    return node


def dump_xml(value: Any) -> str:
    """Serialize the XML mapping back to XML."""
    if not isinstance(value, dict) or len(value) != 1:
        raise OperationTypeError("XML output requires a top-level dict containing exactly one root element.")
    root_tag, root_value = next(iter(value.items()))
    root = _value_to_xml_element(str(root_tag), root_value)
    return element_tree.tostring(root, encoding="unicode")


def _value_to_xml_element(tag: str, value: Any) -> element_tree.Element:
    element = element_tree.Element(tag)
    if isinstance(value, dict):
        attributes = value.get("@attrs", {})
        if attributes:
            if not isinstance(attributes, dict):
                raise OperationTypeError("XML @attrs must be a dict.")
            for attribute_name, attribute_value in attributes.items():
                element.set(str(attribute_name), scalar_to_text(attribute_value))
        text_value = value.get("#text")
        if text_value is not None:
            element.text = scalar_to_text(text_value)
        for child_tag, child_value in value.items():
            if child_tag in {"@attrs", "#text", "#tail"}:
                continue
            if isinstance(child_value, list):
                for item in child_value:
                    element.append(_value_to_xml_element(str(child_tag), item))
            else:
                element.append(_value_to_xml_element(str(child_tag), child_value))
        return element
    if isinstance(value, list):
        raise OperationTypeError("XML elements cannot directly serialize list values without a wrapping tag.")
    element.text = scalar_to_text(value)
    return element


def dump_bmn(value: Any, *, name: str = "data") -> str:
    """Serialize a value as Bash Map Notation."""
    if isinstance(value, dict):
        lines = [f"declare -A {name}=("]
        for key, item in value.items():
            if isinstance(item, (dict, list, tuple, set)):
                raise OperationTypeError("Bash associative arrays only support flat dicts of scalar values.")
            lines.append(f"  [{shlex.quote(scalar_to_text(key))}]={shlex.quote(scalar_to_text(item))}")
        lines.append(")")
        return "\n".join(lines)
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, (dict, list, tuple, set)):
                raise OperationTypeError("Bash arrays only support scalar values.")
        parts = " ".join(shlex.quote(scalar_to_text(item)) for item in value)
        return f"{name}=({parts})"
    raise OperationTypeError("Bash Map Notation output requires a flat dict or a list/tuple of scalars.")


def parse_bmn(source_text: str) -> Any:
    """Parse the limited BMN syntax emitted by this CLI."""
    assoc_match = re.fullmatch(r"\s*declare\s+-A\s+\w+\s*=\s*\((?P<body>.*)\)\s*", source_text, re.DOTALL)
    if assoc_match:
        body = assoc_match.group("body")
        result: dict[str, str] = {}
        for token in shlex.split(body, posix=True):
            match = re.fullmatch(r"\[(?P<key>.*)\]=(?P<value>.*)", token)
            if not match:
                raise InputParseError(f"Could not parse BMN associative entry: {token}")
            result[match.group("key")] = match.group("value")
        return result

    array_match = re.fullmatch(r"\s*\w+\s*=\s*\((?P<body>.*)\)\s*", source_text, re.DOTALL)
    if array_match:
        return shlex.split(array_match.group("body"), posix=True)

    raise InputParseError("Could not parse BMN input.")


def scalar_to_text(value: Any) -> str:
    """Convert scalar values to a textual representation."""
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OperationTypeError("Bytes values must be valid UTF-8 for this output mode.") from exc
    if value is None:
        return "None"
    return str(value)
