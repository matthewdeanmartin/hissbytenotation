use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyFloat, PyList, PySet, PyString, PyTuple};

type PyObject = Py<PyAny>;

/// Error type for parse failures.
#[derive(Debug)]
struct ParseError {
    msg: String,
    pos: usize,
}

impl ParseError {
    fn new(msg: impl Into<String>, pos: usize) -> Self {
        ParseError {
            msg: msg.into(),
            pos,
        }
    }
}

impl From<ParseError> for PyErr {
    fn from(e: ParseError) -> PyErr {
        pyo3::exceptions::PyValueError::new_err(format!(
            "Parse error at position {}: {}",
            e.pos, e.msg
        ))
    }
}

/// A fast recursive-descent parser for Python literal expressions.
///
/// Supports: str, bytes, int, float, bool, None, Ellipsis, tuple, list, set, frozenset, dict.
struct Parser<'a> {
    input: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn new(input: &'a str) -> Self {
        Parser {
            input: input.as_bytes(),
            pos: 0,
        }
    }

    fn remaining(&self) -> usize {
        self.input.len() - self.pos
    }

    fn peek(&self) -> Option<u8> {
        if self.pos < self.input.len() {
            Some(self.input[self.pos])
        } else {
            None
        }
    }

    fn advance(&mut self) {
        self.pos += 1;
    }

    fn skip_whitespace(&mut self) {
        while self.pos < self.input.len() {
            match self.input[self.pos] {
                b' ' | b'\t' | b'\n' | b'\r' => self.pos += 1,
                _ => break,
            }
        }
    }

    fn expect(&mut self, ch: u8) -> Result<(), ParseError> {
        self.skip_whitespace();
        if self.peek() == Some(ch) {
            self.advance();
            Ok(())
        } else {
            Err(ParseError::new(
                format!(
                    "expected '{}', got {:?}",
                    ch as char,
                    self.peek().map(|c| c as char)
                ),
                self.pos,
            ))
        }
    }

    fn starts_with(&self, s: &[u8]) -> bool {
        self.remaining() >= s.len() && &self.input[self.pos..self.pos + s.len()] == s
    }

    /// Check that keyword ends (not followed by alphanumeric/underscore).
    fn keyword_boundary(&self, keyword_len: usize) -> bool {
        let end = self.pos + keyword_len;
        if end >= self.input.len() {
            return true;
        }
        let ch = self.input[end];
        !(ch.is_ascii_alphanumeric() || ch == b'_')
    }

    /// Parse a complete value. Returns an owned PyObject.
    fn parse_value(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        self.skip_whitespace();
        match self.peek() {
            None => Err(ParseError::new("unexpected end of input", self.pos)),
            Some(b'{') => self.parse_dict_or_set(py),
            Some(b'[') => self.parse_list(py),
            Some(b'(') => self.parse_tuple(py),
            Some(b'\'') | Some(b'"') => self.parse_string(py),
            Some(b'b') if self.pos + 1 < self.input.len()
                && (self.input[self.pos + 1] == b'\'' || self.input[self.pos + 1] == b'"') =>
            {
                self.parse_bytes(py)
            }
            Some(b'T') if self.starts_with(b"True") && self.keyword_boundary(4) => {
                self.pos += 4;
                Ok(true.into_pyobject(py).unwrap().to_owned().into_any().unbind())
            }
            Some(b'F') if self.starts_with(b"False") && self.keyword_boundary(5) => {
                self.pos += 5;
                Ok(false.into_pyobject(py).unwrap().to_owned().into_any().unbind())
            }
            Some(b'N') if self.starts_with(b"None") && self.keyword_boundary(4) => {
                self.pos += 4;
                Ok(py.None())
            }
            Some(b'.') if self.starts_with(b"...") => {
                self.pos += 3;
                Ok(py.Ellipsis())
            }
            Some(b'E') if self.starts_with(b"Ellipsis") && self.keyword_boundary(8) => {
                self.pos += 8;
                Ok(py.Ellipsis())
            }
            Some(b'f') if self.starts_with(b"frozenset(") => self.parse_frozenset(py),
            Some(b'-') | Some(b'0'..=b'9') => self.parse_number(py),
            Some(ch) => Err(ParseError::new(
                format!("unexpected character: '{}'", ch as char),
                self.pos,
            )),
        }
    }

    /// Parse a string literal (single or double quoted, with triple-quote support).
    fn parse_string(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        let s = self.parse_string_raw()?;
        Ok(PyString::new(py, &s).into_any().unbind())
    }

    /// Parse the raw string content handling escapes.
    fn parse_string_raw(&mut self) -> Result<String, ParseError> {
        let quote = self.input[self.pos];
        self.advance();

        // Check for triple quote
        let triple = if self.pos + 1 < self.input.len()
            && self.input[self.pos] == quote
            && self.input[self.pos + 1] == quote
        {
            self.pos += 2;
            true
        } else {
            false
        };

        let mut result = String::new();
        loop {
            if self.pos >= self.input.len() {
                return Err(ParseError::new("unterminated string", self.pos));
            }

            if triple {
                if self.remaining() >= 3
                    && self.input[self.pos] == quote
                    && self.input[self.pos + 1] == quote
                    && self.input[self.pos + 2] == quote
                {
                    self.pos += 3;
                    return Ok(result);
                }
            } else if self.input[self.pos] == quote {
                self.advance();
                return Ok(result);
            }

            if self.input[self.pos] == b'\\' {
                self.advance();
                if self.pos >= self.input.len() {
                    return Err(ParseError::new("unterminated escape", self.pos));
                }
                match self.input[self.pos] {
                    b'\\' => result.push('\\'),
                    b'\'' => result.push('\''),
                    b'"' => result.push('"'),
                    b'n' => result.push('\n'),
                    b'r' => result.push('\r'),
                    b't' => result.push('\t'),
                    b'0' => result.push('\0'),
                    b'a' => result.push('\x07'),
                    b'b' => result.push('\x08'),
                    b'f' => result.push('\x0C'),
                    b'v' => result.push('\x0B'),
                    b'x' => {
                        self.advance();
                        let hex = self.read_hex_chars(2)?;
                        let val = u32::from_str_radix(&hex, 16)
                            .map_err(|_| ParseError::new("invalid hex escape", self.pos))?;
                        result.push(
                            char::from_u32(val)
                                .ok_or_else(|| ParseError::new("invalid char from hex", self.pos))?,
                        );
                        continue;
                    }
                    b'u' => {
                        self.advance();
                        let hex = self.read_hex_chars(4)?;
                        let val = u32::from_str_radix(&hex, 16)
                            .map_err(|_| ParseError::new("invalid unicode escape", self.pos))?;
                        result.push(
                            char::from_u32(val)
                                .ok_or_else(|| ParseError::new("invalid unicode char", self.pos))?,
                        );
                        continue;
                    }
                    b'U' => {
                        self.advance();
                        let hex = self.read_hex_chars(8)?;
                        let val = u32::from_str_radix(&hex, 16)
                            .map_err(|_| ParseError::new("invalid unicode escape", self.pos))?;
                        result.push(
                            char::from_u32(val)
                                .ok_or_else(|| ParseError::new("invalid unicode char", self.pos))?,
                        );
                        continue;
                    }
                    c @ b'1'..=b'7' => {
                        let mut oct = String::new();
                        oct.push(c as char);
                        for _ in 0..2 {
                            if self.pos + 1 < self.input.len()
                                && self.input[self.pos + 1] >= b'0'
                                && self.input[self.pos + 1] <= b'7'
                            {
                                self.advance();
                                oct.push(self.input[self.pos] as char);
                            } else {
                                break;
                            }
                        }
                        let val = u32::from_str_radix(&oct, 8)
                            .map_err(|_| ParseError::new("invalid octal escape", self.pos))?;
                        result.push(
                            char::from_u32(val)
                                .ok_or_else(|| ParseError::new("invalid char from octal", self.pos))?,
                        );
                    }
                    b'\n' => {
                        // Line continuation - skip
                    }
                    other => {
                        result.push('\\');
                        result.push(other as char);
                    }
                }
                self.advance();
            } else {
                // Regular character - handle UTF-8
                let byte = self.input[self.pos];
                let char_len = if byte < 0x80 {
                    1
                } else if byte < 0xE0 {
                    2
                } else if byte < 0xF0 {
                    3
                } else {
                    4
                };
                if self.pos + char_len > self.input.len() {
                    return Err(ParseError::new("invalid UTF-8", self.pos));
                }
                let start = self.pos;
                let s = std::str::from_utf8(&self.input[start..start + char_len])
                    .map_err(|_| ParseError::new("invalid UTF-8", self.pos))?;
                result.push_str(s);
                self.pos += char_len;
            }
        }
    }

    fn read_hex_chars(&mut self, count: usize) -> Result<String, ParseError> {
        let mut hex = String::new();
        for _ in 0..count {
            if self.pos >= self.input.len() {
                return Err(ParseError::new("unterminated hex escape", self.pos));
            }
            hex.push(self.input[self.pos] as char);
            self.advance();
        }
        Ok(hex)
    }

    /// Parse a bytes literal: b'...' or b"..."
    fn parse_bytes(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        self.advance(); // skip 'b'
        let s = self.parse_bytes_raw()?;
        Ok(PyBytes::new(py, &s).into_any().unbind())
    }

    fn parse_bytes_raw(&mut self) -> Result<Vec<u8>, ParseError> {
        let quote = self.input[self.pos];
        self.advance();

        let triple = if self.pos + 1 < self.input.len()
            && self.input[self.pos] == quote
            && self.input[self.pos + 1] == quote
        {
            self.pos += 2;
            true
        } else {
            false
        };

        let mut result = Vec::new();
        loop {
            if self.pos >= self.input.len() {
                return Err(ParseError::new("unterminated bytes literal", self.pos));
            }

            if triple {
                if self.remaining() >= 3
                    && self.input[self.pos] == quote
                    && self.input[self.pos + 1] == quote
                    && self.input[self.pos + 2] == quote
                {
                    self.pos += 3;
                    return Ok(result);
                }
            } else if self.input[self.pos] == quote {
                self.advance();
                return Ok(result);
            }

            if self.input[self.pos] == b'\\' {
                self.advance();
                if self.pos >= self.input.len() {
                    return Err(ParseError::new("unterminated escape in bytes", self.pos));
                }
                match self.input[self.pos] {
                    b'\\' => result.push(b'\\'),
                    b'\'' => result.push(b'\''),
                    b'"' => result.push(b'"'),
                    b'n' => result.push(b'\n'),
                    b'r' => result.push(b'\r'),
                    b't' => result.push(b'\t'),
                    b'0' => result.push(0),
                    b'a' => result.push(0x07),
                    b'b' => result.push(0x08),
                    b'f' => result.push(0x0C),
                    b'v' => result.push(0x0B),
                    b'x' => {
                        self.advance();
                        let hex = self.read_hex_chars(2)?;
                        let val = u8::from_str_radix(&hex, 16)
                            .map_err(|_| ParseError::new("invalid hex escape in bytes", self.pos))?;
                        result.push(val);
                        continue;
                    }
                    c @ b'1'..=b'7' => {
                        let mut oct = String::new();
                        oct.push(c as char);
                        for _ in 0..2 {
                            if self.pos + 1 < self.input.len()
                                && self.input[self.pos + 1] >= b'0'
                                && self.input[self.pos + 1] <= b'7'
                            {
                                self.advance();
                                oct.push(self.input[self.pos] as char);
                            } else {
                                break;
                            }
                        }
                        let val = u8::from_str_radix(&oct, 8)
                            .map_err(|_| ParseError::new("invalid octal escape in bytes", self.pos))?;
                        result.push(val);
                    }
                    other => {
                        result.push(b'\\');
                        result.push(other);
                    }
                }
                self.advance();
            } else {
                result.push(self.input[self.pos]);
                self.advance();
            }
        }
    }

    /// Parse a number (int or float, including negative).
    fn parse_number(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        let start = self.pos;
        let mut is_float = false;

        if self.peek() == Some(b'-') {
            self.advance();
        }

        // Hex, octal, binary prefixes
        if self.peek() == Some(b'0') && self.pos + 1 < self.input.len() {
            match self.input[self.pos + 1] {
                b'x' | b'X' => {
                    self.pos += 2;
                    while self.pos < self.input.len()
                        && (self.input[self.pos].is_ascii_hexdigit() || self.input[self.pos] == b'_')
                    {
                        self.advance();
                    }
                    let num_str: String = std::str::from_utf8(&self.input[start..self.pos])
                        .unwrap()
                        .chars()
                        .filter(|c| *c != '_')
                        .collect();
                    let stripped = num_str.trim_start_matches('-').trim_start_matches("0x").trim_start_matches("0X");
                    let val = i64::from_str_radix(stripped, 16)
                        .map_err(|_| ParseError::new("invalid hex number", start))?;
                    let val = if num_str.starts_with('-') { -val } else { val };
                    return Ok(val.into_pyobject(py).unwrap().into_any().unbind());
                }
                b'o' | b'O' => {
                    self.pos += 2;
                    while self.pos < self.input.len()
                        && ((self.input[self.pos] >= b'0' && self.input[self.pos] <= b'7')
                            || self.input[self.pos] == b'_')
                    {
                        self.advance();
                    }
                    let num_str: String = std::str::from_utf8(&self.input[start..self.pos])
                        .unwrap()
                        .chars()
                        .filter(|c| *c != '_')
                        .collect();
                    let stripped = num_str.trim_start_matches('-').trim_start_matches("0o").trim_start_matches("0O");
                    let val = i64::from_str_radix(stripped, 8)
                        .map_err(|_| ParseError::new("invalid octal number", start))?;
                    let val = if num_str.starts_with('-') { -val } else { val };
                    return Ok(val.into_pyobject(py).unwrap().into_any().unbind());
                }
                b'b' | b'B' => {
                    self.pos += 2;
                    while self.pos < self.input.len()
                        && (self.input[self.pos] == b'0' || self.input[self.pos] == b'1' || self.input[self.pos] == b'_')
                    {
                        self.advance();
                    }
                    let num_str: String = std::str::from_utf8(&self.input[start..self.pos])
                        .unwrap()
                        .chars()
                        .filter(|c| *c != '_')
                        .collect();
                    let stripped = num_str.trim_start_matches('-').trim_start_matches("0b").trim_start_matches("0B");
                    let val = i64::from_str_radix(stripped, 2)
                        .map_err(|_| ParseError::new("invalid binary number", start))?;
                    let val = if num_str.starts_with('-') { -val } else { val };
                    return Ok(val.into_pyobject(py).unwrap().into_any().unbind());
                }
                _ => {}
            }
        }

        // Digits
        while self.pos < self.input.len()
            && (self.input[self.pos].is_ascii_digit() || self.input[self.pos] == b'_')
        {
            self.advance();
        }

        // Decimal point
        if self.pos < self.input.len() && self.input[self.pos] == b'.' {
            is_float = true;
            self.advance();
            while self.pos < self.input.len()
                && (self.input[self.pos].is_ascii_digit() || self.input[self.pos] == b'_')
            {
                self.advance();
            }
        }

        // Exponent
        if self.pos < self.input.len() && (self.input[self.pos] == b'e' || self.input[self.pos] == b'E') {
            is_float = true;
            self.advance();
            if self.pos < self.input.len() && (self.input[self.pos] == b'+' || self.input[self.pos] == b'-') {
                self.advance();
            }
            while self.pos < self.input.len()
                && (self.input[self.pos].is_ascii_digit() || self.input[self.pos] == b'_')
            {
                self.advance();
            }
        }

        let num_str: String = std::str::from_utf8(&self.input[start..self.pos])
            .map_err(|_| ParseError::new("invalid number", start))?
            .chars()
            .filter(|c| *c != '_')
            .collect();

        if is_float {
            let val: f64 = num_str
                .parse()
                .map_err(|_| ParseError::new("invalid float", start))?;
            Ok(PyFloat::new(py, val).into_any().unbind())
        } else {
            match num_str.parse::<i64>() {
                Ok(val) => Ok(val.into_pyobject(py).unwrap().into_any().unbind()),
                Err(_) => {
                    // Use Python's int() for big integers
                    let builtins = py.import("builtins")
                        .map_err(|_| ParseError::new("failed to import builtins", start))?;
                    let int_fn = builtins.getattr("int")
                        .map_err(|_| ParseError::new("failed to get int", start))?;
                    let result = int_fn.call1((&num_str,))
                        .map_err(|_| ParseError::new("failed to parse big int", start))?;
                    Ok(result.unbind())
                }
            }
        }
    }

    /// Parse a list: [item, item, ...]
    fn parse_list(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        self.expect(b'[')?;
        let mut items: Vec<PyObject> = Vec::new();

        self.skip_whitespace();
        if self.peek() == Some(b']') {
            self.advance();
            let list = PyList::empty(py);
            return Ok(list.into_any().unbind());
        }

        loop {
            items.push(self.parse_value(py)?);
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => {
                    self.advance();
                    self.skip_whitespace();
                    if self.peek() == Some(b']') {
                        self.advance();
                        break;
                    }
                }
                Some(b']') => {
                    self.advance();
                    break;
                }
                _ => return Err(ParseError::new("expected ',' or ']' in list", self.pos)),
            }
        }

        let list = PyList::empty(py);
        for item in items {
            list.append(item).map_err(|_| ParseError::new("failed to append to list", self.pos))?;
        }
        Ok(list.into_any().unbind())
    }

    /// Parse a tuple: (item, item, ...) or (item,) for single-element
    fn parse_tuple(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        self.expect(b'(')?;
        let mut items: Vec<PyObject> = Vec::new();
        let mut has_comma = false;

        self.skip_whitespace();
        if self.peek() == Some(b')') {
            self.advance();
            let tuple = PyTuple::empty(py);
            return Ok(tuple.into_any().unbind());
        }

        loop {
            items.push(self.parse_value(py)?);
            self.skip_whitespace();
            match self.peek() {
                Some(b',') => {
                    has_comma = true;
                    self.advance();
                    self.skip_whitespace();
                    if self.peek() == Some(b')') {
                        self.advance();
                        break;
                    }
                }
                Some(b')') => {
                    self.advance();
                    // Single item without trailing comma = parenthesized expression
                    if items.len() == 1 && !has_comma {
                        return Ok(items.into_iter().next().unwrap());
                    }
                    break;
                }
                _ => return Err(ParseError::new("expected ',' or ')' in tuple", self.pos)),
            }
        }

        let refs: Vec<&PyObject> = items.iter().collect();
        let tuple = PyTuple::new(py, &refs)
            .map_err(|_| ParseError::new("failed to create tuple", self.pos))?;
        Ok(tuple.into_any().unbind())
    }

    /// Parse a dict or set: { ... }
    fn parse_dict_or_set(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        self.expect(b'{')?;
        self.skip_whitespace();

        // Empty dict
        if self.peek() == Some(b'}') {
            self.advance();
            let dict = PyDict::new(py);
            return Ok(dict.into_any().unbind());
        }

        // Parse first value
        let first = self.parse_value(py)?;
        self.skip_whitespace();

        match self.peek() {
            Some(b':') => {
                // It's a dict
                self.advance();
                let val = self.parse_value(py)?;
                let dict = PyDict::new(py);
                dict.set_item(&first, &val)
                    .map_err(|_| ParseError::new("failed to set dict item", self.pos))?;

                self.skip_whitespace();
                loop {
                    match self.peek() {
                        Some(b',') => {
                            self.advance();
                            self.skip_whitespace();
                            if self.peek() == Some(b'}') {
                                self.advance();
                                break;
                            }
                            let key = self.parse_value(py)?;
                            self.skip_whitespace();
                            self.expect(b':')?;
                            let val = self.parse_value(py)?;
                            dict.set_item(&key, &val)
                                .map_err(|_| ParseError::new("failed to set dict item", self.pos))?;
                            self.skip_whitespace();
                        }
                        Some(b'}') => {
                            self.advance();
                            break;
                        }
                        _ => return Err(ParseError::new("expected ',' or '}' in dict", self.pos)),
                    }
                }
                Ok(dict.into_any().unbind())
            }
            Some(b',') | Some(b'}') => {
                // It's a set
                let set = PySet::empty(py)
                    .map_err(|_| ParseError::new("failed to create set", self.pos))?;
                set.add(&first)
                    .map_err(|_| ParseError::new("failed to add to set", self.pos))?;

                if self.peek() == Some(b'}') {
                    self.advance();
                    return Ok(set.into_any().unbind());
                }
                // Skip the comma
                self.advance();
                self.skip_whitespace();

                if self.peek() == Some(b'}') {
                    self.advance();
                    return Ok(set.into_any().unbind());
                }

                loop {
                    let item = self.parse_value(py)?;
                    set.add(&item)
                        .map_err(|_| ParseError::new("failed to add to set", self.pos))?;
                    self.skip_whitespace();
                    match self.peek() {
                        Some(b',') => {
                            self.advance();
                            self.skip_whitespace();
                            if self.peek() == Some(b'}') {
                                self.advance();
                                break;
                            }
                        }
                        Some(b'}') => {
                            self.advance();
                            break;
                        }
                        _ => return Err(ParseError::new("expected ',' or '}' in set", self.pos)),
                    }
                }

                Ok(set.into_any().unbind())
            }
            _ => Err(ParseError::new(
                "expected ':', ',' or '}' after first element in dict/set",
                self.pos,
            )),
        }
    }

    /// Parse frozenset({...})
    fn parse_frozenset(&mut self, py: Python<'_>) -> Result<PyObject, ParseError> {
        if !self.starts_with(b"frozenset(") {
            return Err(ParseError::new("expected 'frozenset('", self.pos));
        }
        self.pos += 10;
        self.skip_whitespace();

        let inner = self.parse_value(py)?;
        self.skip_whitespace();
        self.expect(b')')?;

        let builtins = py.import("builtins")
            .map_err(|_| ParseError::new("failed to import builtins", self.pos))?;
        let frozenset_fn = builtins.getattr("frozenset")
            .map_err(|_| ParseError::new("failed to get frozenset", self.pos))?;
        let result = frozenset_fn.call1((inner,))
            .map_err(|_| ParseError::new("failed to create frozenset from iterable", self.pos))?;
        Ok(result.unbind())
    }
}

/// Parse a Python literal expression string into a Python object.
///
/// This is a Rust-accelerated replacement for ast.literal_eval().
/// It supports: str, bytes, int, float, bool, None, Ellipsis,
/// tuple, list, set, frozenset, and dict (all nested).
///
/// It is safe: no arbitrary code execution, only literal parsing.
#[pyfunction]
fn loads(py: Python<'_>, source: &str) -> PyResult<Py<PyAny>> {
    let mut parser = Parser::new(source);
    let result = parser.parse_value(py)?;
    parser.skip_whitespace();
    if parser.pos != parser.input.len() {
        return Err(pyo3::exceptions::PyValueError::new_err(format!(
            "Trailing content at position {}",
            parser.pos
        )));
    }
    Ok(result)
}

/// A Python module implemented in Rust.
#[pymodule]
fn hbn_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(loads, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::loads;
    use pyo3::prelude::*;

    #[test]
    fn matches_ast_literal_eval_for_supported_literals() {
        Python::initialize();
        Python::attach(|py| {
            let ast = py.import("ast").unwrap();
            let literal_eval = ast.getattr("literal_eval").unwrap();
            let cases = [
                "42",
                "-7",
                "3.14",
                "'hello'",
                "b'bytes'",
                "True",
                "False",
                "None",
                "...",
                "(1, 2, 3)",
                "[1, 'two', 3.0]",
                "{'a': 1, 'b': [2, 3]}",
                "{'nested': {'deep': (1, 2)}}",
                "[]",
                "{}",
                "()",
                "(42,)",
                "(42)",
            ];

            for case in cases {
                let rust_value = loads(py, case).unwrap();
                let python_value = literal_eval.call1((case,)).unwrap();
                assert!(
                    rust_value.bind(py).eq(python_value).unwrap(),
                    "parser result differed from ast.literal_eval for {case}"
                );
            }
        });
    }

    #[test]
    fn parses_numeric_variants_and_large_integers() {
        Python::initialize();
        Python::attach(|py| {
            assert_eq!(loads(py, "0xff").unwrap().bind(py).extract::<i64>().unwrap(), 255);
            assert_eq!(loads(py, "-0o10").unwrap().bind(py).extract::<i64>().unwrap(), -8);
            assert_eq!(loads(py, "0b1010_0101").unwrap().bind(py).extract::<i64>().unwrap(), 165);
            assert_eq!(loads(py, "1_000_000").unwrap().bind(py).extract::<i64>().unwrap(), 1_000_000);

            let float_value = loads(py, "-1.25e2").unwrap().bind(py).extract::<f64>().unwrap();
            assert_eq!(float_value, -125.0);

            let big_int = "1234567890123456789012345678901234567890";
            let parsed = loads(py, big_int).unwrap();
            assert_eq!(
                parsed.bind(py).str().unwrap().to_string_lossy().as_ref(),
                big_int
            );
        });
    }

    #[test]
    fn parses_triple_quoted_strings_and_bytes_escapes() {
        Python::initialize();
        Python::attach(|py| {
            let triple = loads(py, r#"'''hello\nworld'''"#).unwrap();
            assert_eq!(
                triple.bind(py).extract::<String>().unwrap(),
                "hello\nworld"
            );

            let bytes_value = loads(py, r#"b'\x68\151'"#).unwrap();
            assert_eq!(bytes_value.bind(py).extract::<Vec<u8>>().unwrap(), b"hi");
        });
    }

    #[test]
    fn parses_frozenset_and_ellipsis_alias() {
        Python::initialize();
        Python::attach(|py| {
            let ellipsis = loads(py, "Ellipsis").unwrap();
            assert_eq!(
                ellipsis.bind(py).repr().unwrap().to_string_lossy().as_ref(),
                "Ellipsis"
            );

            let frozen = loads(py, "frozenset({3, 1, 2})").unwrap();
            assert_eq!(
                frozen
                    .bind(py)
                    .get_type()
                    .name()
                    .unwrap()
                    .to_str()
                    .unwrap(),
                "frozenset"
            );

            let builtins = py.import("builtins").unwrap();
            let sorted = builtins.getattr("sorted").unwrap();
            let items: Vec<i64> = sorted.call1((frozen.bind(py),)).unwrap().extract().unwrap();
            assert_eq!(items, vec![1, 2, 3]);
        });
    }

    #[test]
    fn rejects_invalid_input_with_useful_errors() {
        Python::initialize();
        Python::attach(|py| {
            let cases = [
                ("'unterminated", "unterminated string"),
                (r#"b'\xzz'"#, "invalid hex escape in bytes"),
                ("[1 2]", "expected ',' or ']' in list"),
                ("1 2", "Trailing content"),
            ];

            for (case, expected) in cases {
                let error = loads(py, case).unwrap_err();
                assert!(
                    error.to_string().contains(expected),
                    "expected error containing {expected:?} for {case:?}, got {error}"
                );
            }
        });
    }
}
