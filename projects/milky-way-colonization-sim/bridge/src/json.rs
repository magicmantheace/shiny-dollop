//! Minimal JSON value type with a full parser and serializer.
//!
//! Zero third-party crates by design (the build environment is
//! offline). The parser never panics on input: every malformed input
//! produces an `Err` with a position-tagged message.

use std::fmt;

#[derive(Debug, Clone, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Number(f64),
    String(String),
    Array(Vec<Value>),
    Object(Vec<(String, Value)>),
}

impl Value {
    pub fn obj(pairs: Vec<(&str, Value)>) -> Value {
        Value::Object(
            pairs
                .into_iter()
                .map(|(k, v)| (k.to_string(), v))
                .collect(),
        )
    }

    pub fn get(&self, key: &str) -> Option<&Value> {
        match self {
            Value::Object(pairs) => pairs.iter().rev().find(|(k, _)| k == key).map(|(_, v)| v),
            _ => None,
        }
    }

    pub fn as_str(&self) -> Result<&str, String> {
        match self {
            Value::String(s) => Ok(s),
            other => Err(format!("expected string, found {}", other.type_name())),
        }
    }

    pub fn as_f64(&self) -> Result<f64, String> {
        match self {
            Value::Number(n) => Ok(*n),
            other => Err(format!("expected number, found {}", other.type_name())),
        }
    }

    pub fn as_u64(&self) -> Result<u64, String> {
        let n = self.as_f64()?;
        if !n.is_finite() || n < 0.0 || n.fract() != 0.0 || n > u64::MAX as f64 {
            return Err(format!("expected unsigned integer, found {n}"));
        }
        Ok(n as u64)
    }

    pub fn as_bool(&self) -> Result<bool, String> {
        match self {
            Value::Bool(b) => Ok(*b),
            other => Err(format!("expected bool, found {}", other.type_name())),
        }
    }

    pub fn as_array(&self) -> Result<&[Value], String> {
        match self {
            Value::Array(items) => Ok(items),
            other => Err(format!("expected array, found {}", other.type_name())),
        }
    }

    pub fn as_object(&self) -> Result<&Vec<(String, Value)>, String> {
        match self {
            Value::Object(pairs) => Ok(pairs),
            other => Err(format!("expected object, found {}", other.type_name())),
        }
    }

    pub fn type_name(&self) -> &'static str {
        match self {
            Value::Null => "null",
            Value::Bool(_) => "bool",
            Value::Number(_) => "number",
            Value::String(_) => "string",
            Value::Array(_) => "array",
            Value::Object(_) => "object",
        }
    }

    /// Serialize to JSON text. Non-finite numbers serialize as `null`
    /// (JSON has no NaN/Infinity literal).
    pub fn to_json_string(&self) -> String {
        let mut out = String::new();
        self.write_to(&mut out);
        out
    }

    fn write_to(&self, out: &mut String) {
        match self {
            Value::Null => out.push_str("null"),
            Value::Bool(true) => out.push_str("true"),
            Value::Bool(false) => out.push_str("false"),
            Value::Number(n) => {
                if n.is_finite() {
                    // Rust's Display for f64 round-trips.
                    out.push_str(&format!("{n}"));
                } else {
                    out.push_str("null");
                }
            }
            Value::String(s) => write_json_string(s, out),
            Value::Array(items) => {
                out.push('[');
                for (i, item) in items.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    item.write_to(out);
                }
                out.push(']');
            }
            Value::Object(pairs) => {
                out.push('{');
                for (i, (k, v)) in pairs.iter().enumerate() {
                    if i > 0 {
                        out.push(',');
                    }
                    write_json_string(k, out);
                    out.push(':');
                    v.write_to(out);
                }
                out.push('}');
            }
        }
    }
}

impl fmt::Display for Value {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.to_json_string())
    }
}

impl From<&str> for Value {
    fn from(s: &str) -> Self {
        Value::String(s.to_string())
    }
}
impl From<String> for Value {
    fn from(s: String) -> Self {
        Value::String(s)
    }
}
impl From<f64> for Value {
    fn from(n: f64) -> Self {
        Value::Number(n)
    }
}
impl From<u64> for Value {
    fn from(n: u64) -> Self {
        Value::Number(n as f64)
    }
}
impl From<u32> for Value {
    fn from(n: u32) -> Self {
        Value::Number(n as f64)
    }
}
impl From<usize> for Value {
    fn from(n: usize) -> Self {
        Value::Number(n as f64)
    }
}
impl From<bool> for Value {
    fn from(b: bool) -> Self {
        Value::Bool(b)
    }
}

fn write_json_string(s: &str, out: &mut String) {
    out.push('"');
    for ch in s.chars() {
        match ch {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => {
                out.push_str(&format!("\\u{:04x}", c as u32));
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

pub fn parse(input: &str) -> Result<Value, String> {
    let mut parser = Parser {
        bytes: input.as_bytes(),
        pos: 0,
    };
    parser.skip_ws();
    let value = parser.parse_value()?;
    parser.skip_ws();
    if parser.pos != parser.bytes.len() {
        return Err(format!(
            "trailing characters at byte {}",
            parser.pos
        ));
    }
    Ok(value)
}

struct Parser<'a> {
    bytes: &'a [u8],
    pos: usize,
}

impl<'a> Parser<'a> {
    fn err(&self, msg: &str) -> String {
        format!("{msg} at byte {}", self.pos)
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn bump(&mut self) -> Option<u8> {
        let b = self.peek()?;
        self.pos += 1;
        Some(b)
    }

    fn skip_ws(&mut self) {
        while let Some(b) = self.peek() {
            if b == b' ' || b == b'\t' || b == b'\n' || b == b'\r' {
                self.pos += 1;
            } else {
                break;
            }
        }
    }

    fn expect(&mut self, b: u8) -> Result<(), String> {
        if self.bump() == Some(b) {
            Ok(())
        } else {
            Err(self.err(&format!("expected '{}'", b as char)))
        }
    }

    fn parse_value(&mut self) -> Result<Value, String> {
        self.skip_ws();
        match self.peek() {
            Some(b'{') => self.parse_object(),
            Some(b'[') => self.parse_array(),
            Some(b'"') => Ok(Value::String(self.parse_string()?)),
            Some(b't') => self.parse_literal("true", Value::Bool(true)),
            Some(b'f') => self.parse_literal("false", Value::Bool(false)),
            Some(b'n') => self.parse_literal("null", Value::Null),
            Some(b'-') | Some(b'0'..=b'9') => self.parse_number(),
            Some(other) => Err(self.err(&format!(
                "unexpected character '{}'",
                other as char
            ))),
            None => Err(self.err("unexpected end of input")),
        }
    }

    fn parse_literal(&mut self, lit: &str, value: Value) -> Result<Value, String> {
        if self.bytes.len() - self.pos >= lit.len()
            && &self.bytes[self.pos..self.pos + lit.len()] == lit.as_bytes()
        {
            self.pos += lit.len();
            Ok(value)
        } else {
            Err(self.err(&format!("invalid literal, expected {lit}")))
        }
    }

    fn parse_object(&mut self) -> Result<Value, String> {
        self.expect(b'{')?;
        let mut pairs = Vec::new();
        self.skip_ws();
        if self.peek() == Some(b'}') {
            self.pos += 1;
            return Ok(Value::Object(pairs));
        }
        loop {
            self.skip_ws();
            if self.peek() != Some(b'"') {
                return Err(self.err("expected string key in object"));
            }
            let key = self.parse_string()?;
            self.skip_ws();
            self.expect(b':')?;
            let value = self.parse_value()?;
            pairs.push((key, value));
            self.skip_ws();
            match self.bump() {
                Some(b',') => continue,
                Some(b'}') => break,
                _ => return Err(self.err("expected ',' or '}' in object")),
            }
        }
        Ok(Value::Object(pairs))
    }

    fn parse_array(&mut self) -> Result<Value, String> {
        self.expect(b'[')?;
        let mut items = Vec::new();
        self.skip_ws();
        if self.peek() == Some(b']') {
            self.pos += 1;
            return Ok(Value::Array(items));
        }
        loop {
            let value = self.parse_value()?;
            items.push(value);
            self.skip_ws();
            match self.bump() {
                Some(b',') => continue,
                Some(b']') => break,
                _ => return Err(self.err("expected ',' or ']' in array")),
            }
        }
        Ok(Value::Array(items))
    }

    fn parse_string(&mut self) -> Result<String, String> {
        self.expect(b'"')?;
        let mut out = String::new();
        loop {
            let b = match self.bump() {
                Some(b) => b,
                None => return Err(self.err("unterminated string")),
            };
            match b {
                b'"' => break,
                b'\\' => {
                    let esc = match self.bump() {
                        Some(e) => e,
                        None => return Err(self.err("unterminated escape")),
                    };
                    match esc {
                        b'"' => out.push('"'),
                        b'\\' => out.push('\\'),
                        b'/' => out.push('/'),
                        b'b' => out.push('\u{08}'),
                        b'f' => out.push('\u{0c}'),
                        b'n' => out.push('\n'),
                        b'r' => out.push('\r'),
                        b't' => out.push('\t'),
                        b'u' => {
                            let cp = self.parse_unicode_escape()?;
                            match char::from_u32(cp) {
                                Some(ch) => out.push(ch),
                                None => {
                                    return Err(self.err("invalid unicode code point"))
                                }
                            }
                        }
                        other => {
                            return Err(self.err(&format!(
                                "invalid escape '\\{}'",
                                other as char
                            )))
                        }
                    }
                }
                0x00..=0x1f => {
                    return Err(self.err("unescaped control character in string"));
                }
                _ => {
                    // Decode one UTF-8 code point starting at pos-1.
                    let start = self.pos - 1;
                    let len = utf8_len(self.bytes[start]);
                    if start + len > self.bytes.len() {
                        return Err(self.err("truncated UTF-8 in string"));
                    }
                    match std::str::from_utf8(&self.bytes[start..start + len]) {
                        Ok(s) => {
                            out.push_str(s);
                            self.pos = start + len;
                        }
                        Err(_) => return Err(self.err("invalid UTF-8 in string")),
                    }
                }
            }
        }
        Ok(out)
    }

    fn parse_hex4(&mut self) -> Result<u32, String> {
        let mut value: u32 = 0;
        for _ in 0..4 {
            let b = match self.bump() {
                Some(b) => b,
                None => return Err(self.err("truncated \\u escape")),
            };
            let digit = match b {
                b'0'..=b'9' => (b - b'0') as u32,
                b'a'..=b'f' => (b - b'a') as u32 + 10,
                b'A'..=b'F' => (b - b'A') as u32 + 10,
                _ => return Err(self.err("invalid hex digit in \\u escape")),
            };
            value = value * 16 + digit;
        }
        Ok(value)
    }

    fn parse_unicode_escape(&mut self) -> Result<u32, String> {
        let first = self.parse_hex4()?;
        if (0xd800..0xdc00).contains(&first) {
            // High surrogate: a low surrogate must follow.
            if self.bump() == Some(b'\\') && self.peek() == Some(b'u') {
                self.pos += 1; // consume 'u'
                let second = self.parse_hex4()?;
                if (0xdc00..0xe000).contains(&second) {
                    return Ok(0x10000 + ((first - 0xd800) << 10) + (second - 0xdc00));
                }
                return Err(self.err("high surrogate not followed by low surrogate"));
            }
            return Err(self.err("unpaired high surrogate"));
        }
        if (0xdc00..0xe000).contains(&first) {
            return Err(self.err("unpaired low surrogate"));
        }
        Ok(first)
    }

    fn parse_number(&mut self) -> Result<Value, String> {
        let start = self.pos;
        if self.peek() == Some(b'-') {
            self.pos += 1;
        }
        // Integer part.
        match self.peek() {
            Some(b'0') => {
                self.pos += 1;
            }
            Some(b'1'..=b'9') => {
                while matches!(self.peek(), Some(b'0'..=b'9')) {
                    self.pos += 1;
                }
            }
            _ => return Err(self.err("invalid number")),
        }
        // Fraction.
        if self.peek() == Some(b'.') {
            self.pos += 1;
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.err("invalid number: digit required after '.'"));
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        // Exponent.
        if matches!(self.peek(), Some(b'e') | Some(b'E')) {
            self.pos += 1;
            if matches!(self.peek(), Some(b'+') | Some(b'-')) {
                self.pos += 1;
            }
            if !matches!(self.peek(), Some(b'0'..=b'9')) {
                return Err(self.err("invalid number: digit required in exponent"));
            }
            while matches!(self.peek(), Some(b'0'..=b'9')) {
                self.pos += 1;
            }
        }
        let text = match std::str::from_utf8(&self.bytes[start..self.pos]) {
            Ok(t) => t,
            Err(_) => return Err(self.err("invalid number encoding")),
        };
        match text.parse::<f64>() {
            Ok(n) => Ok(Value::Number(n)),
            Err(_) => Err(self.err("invalid number")),
        }
    }
}

fn utf8_len(first: u8) -> usize {
    if first < 0x80 {
        1
    } else if first >> 5 == 0b110 {
        2
    } else if first >> 4 == 0b1110 {
        3
    } else if first >> 3 == 0b11110 {
        4
    } else {
        1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trip_nested() {
        let value = Value::obj(vec![
            ("name", Value::from("Sol \"home\" \\ \n")),
            ("day", Value::from(42u64)),
            ("credits", Value::from(15000.5f64)),
            ("ok", Value::Bool(true)),
            ("nothing", Value::Null),
            (
                "list",
                Value::Array(vec![
                    Value::from(1u64),
                    Value::from("two"),
                    Value::obj(vec![("nested", Value::Array(vec![]))]),
                ]),
            ),
        ]);
        let text = value.to_json_string();
        let back = parse(&text).expect("round-trip parse");
        assert_eq!(value, back);
    }

    #[test]
    fn escapes_and_unicode() {
        let parsed = parse(r#""a\"b\\c\/d\be\ff\ng\rh\ti""#).unwrap();
        assert_eq!(
            parsed,
            Value::String("a\"b\\c/d\u{08}e\u{0c}f\ng\rh\ti".to_string())
        );
        // Raw UTF-8 in strings passes through.
        let parsed = parse(r#""Aé""#).unwrap();
        assert_eq!(parsed, Value::String("Aé".to_string()));
        let parsed = parse(r#""😀""#).unwrap();
        assert_eq!(parsed, Value::String("\u{1f600}".to_string()));
        // BMP escape + surrogate pair (U+1F600), built without a
        // literal escape sequence in this source file.
        let bs = char::from_u32(92).unwrap();
        let mut esc_input = String::from("\"");
        for esc in ["u0041", "ud83d", "ude00", "u00e9"] {
            esc_input.push(bs);
            esc_input.push_str(esc);
        }
        esc_input.push('"');
        let parsed = parse(&esc_input).unwrap();
        assert_eq!(parsed, Value::String("A\u{1f600}é".to_string()));
        let ser = Value::String("tab\tnewline\nquote\"".to_string()).to_json_string();
        assert_eq!(parse(&ser).unwrap(), Value::String("tab\tnewline\nquote\"".to_string()));
        // Control character escapes on serialize.
        let ser = Value::String("\u{01}".to_string()).to_json_string();
        assert_eq!(ser, "\"\\u0001\"");
    }

    #[test]
    fn numbers_round_trip() {
        for text in ["0", "-1", "3.25", "-0.5e3", "1e10", "150", "0.30000000000000004"] {
            let v = parse(text).unwrap();
            let back = parse(&v.to_json_string()).unwrap();
            assert_eq!(v, back, "number {text}");
        }
    }

    #[test]
    fn malformed_inputs_error_without_panic() {
        for bad in [
            "",
            "{",
            "[1,",
            "{\"a\":}",
            "{\"a\":1",
            "\"unterminated",
            "\"bad \\x escape\"",
            "tru",
            "nulll",
            "01",
            "1.",
            "-",
            "[1 2]",
            "{\"a\" 1}",
            "\"\\ud800 lone\"",
            "\"\\udc00 lone\"",
            "{]",
            "123abc",
        ] {
            assert!(parse(bad).is_err(), "expected Err for {bad:?}");
        }
    }

    #[test]
    fn helpers() {
        let v = parse(r#"{"a": 7, "b": "x", "c": [true]}"#).unwrap();
        assert_eq!(v.get("a").unwrap().as_u64().unwrap(), 7);
        assert_eq!(v.get("b").unwrap().as_str().unwrap(), "x");
        assert_eq!(v.get("c").unwrap().as_array().unwrap().len(), 1);
        assert!(v.get("missing").is_none());
        assert!(v.get("a").unwrap().as_str().is_err());
        assert!(v.as_object().is_ok());
    }
}
