//! Minimal RFC 4180 CSV reader: handles quoted fields, embedded commas,
//! doubled quotes, and CRLF/LF line endings. Both source catalogs (HYG,
//! Exoplanet Archive TAP output) are machine-generated CSV of this shape.

/// Parse CSV text into rows of fields. The first row is the header.
pub fn parse_csv(text: &str) -> Vec<Vec<String>> {
    let mut rows: Vec<Vec<String>> = Vec::new();
    let mut row: Vec<String> = Vec::new();
    let mut field: Vec<char> = Vec::new();
    let mut in_quotes = false;
    let mut field_started = false;
    let chars: Vec<char> = text.chars().collect();
    let mut i = 0usize;
    let n = chars.len();

    let push_field = |row: &mut Vec<String>, field: &mut Vec<char>| {
        row.push(field.iter().collect());
        field.clear();
    };

    while i < n {
        let c = chars[i];
        if in_quotes {
            if c == '"' {
                if i + 1 < n && chars[i + 1] == '"' {
                    field.push('"');
                    i += 2;
                } else {
                    in_quotes = false;
                    i += 1;
                }
            } else {
                field.push(c);
                i += 1;
            }
            continue;
        }
        match c {
            '"' if !field_started => {
                in_quotes = true;
                field_started = true;
                i += 1;
            }
            ',' => {
                push_field(&mut row, &mut field);
                field_started = false;
                i += 1;
            }
            '\r' => {
                i += 1; // swallow; the \n (if any) terminates the row
            }
            '\n' => {
                push_field(&mut row, &mut field);
                rows.push(std::mem::take(&mut row));
                field_started = false;
                i += 1;
            }
            _ => {
                field.push(c);
                field_started = true;
                i += 1;
            }
        }
    }
    // Trailing row without a final newline.
    if field_started || !row.is_empty() || in_quotes {
        push_field(&mut row, &mut field);
        if !row.is_empty() {
            rows.push(row);
        }
    }
    rows
}

/// Column index lookup by header name (exact match). Panics with a clear
/// message when a required column is absent — catalog schema drift should
/// fail loudly, never silently mis-map.
pub fn col(header: &[String], name: &str) -> usize {
    header
        .iter()
        .position(|h| h == name)
        .unwrap_or_else(|| panic!("required CSV column '{name}' not found in header {header:?}"))
}

pub fn get(row: &[String], idx: usize) -> &str {
    row.get(idx).map(|s| s.as_str()).unwrap_or("")
}

pub fn parse_f32(s: &str) -> Option<f32> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse::<f32>().ok().filter(|v| v.is_finite())
    }
}

pub fn parse_f64(s: &str) -> Option<f64> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse::<f64>().ok().filter(|v| v.is_finite())
    }
}

pub fn parse_i64(s: &str) -> Option<i64> {
    let s = s.trim();
    if s.is_empty() {
        None
    } else {
        s.parse::<i64>().ok()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn quoted_fields_and_commas() {
        let rows = parse_csv("a,b,c\n\"x,y\",\"he said \"\"hi\"\"\",plain\n");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[1], vec!["x,y", "he said \"hi\"", "plain"]);
    }

    #[test]
    fn crlf_and_no_trailing_newline() {
        let rows = parse_csv("a,b\r\n1,2");
        assert_eq!(rows.len(), 2);
        assert_eq!(rows[1], vec!["1", "2"]);
    }
}
