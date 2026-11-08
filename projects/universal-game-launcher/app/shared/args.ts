/**
 * Parse a human-typed argument string into an argv array.
 * Supports double quotes, single quotes, and backslash escapes.
 * Pure function — safe to use in renderer and main.
 *
 *   --fullscreen --level 3            -> ['--fullscreen', '--level', '3']
 *   --name "My Game"                 -> ['--name', 'My Game']
 *   --path 'C:\\Games\\x'             -> ['--path', 'C:\\Games\\x']
 *
 * Throws ArgsParseError on unterminated quotes.
 */
export class ArgsParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ArgsParseError';
  }
}

/**
 * Serialize an argv array back into the text form parseArgsString
 * accepts — the exact inverse of the parser. Any argument that is empty
 * or contains whitespace, quotes, or backslashes is wrapped in double
 * quotes with `\` and `"` escaped, so parseArgsString(serializeArgs(a))
 * always deep-equals `a`. Joining with plain spaces is NOT reversible:
 * ['--name', 'My Game'] would re-parse as three arguments, and a
 * Windows path's backslashes would be eaten as escape characters.
 */
export function serializeArgs(args: readonly string[]): string {
  return args.map(serializeArg).join(' ');
}

function serializeArg(arg: string): string {
  if (arg.length > 0 && !/[\s"'\\]/.test(arg)) {
    return arg;
  }
  return `"${arg.replace(/\\/g, '\\\\').replace(/"/g, '\\"')}"`;
}

export function parseArgsString(input: string): string[] {
  const args: string[] = [];
  let current = '';
  let quote: '"' | "'" | null = null;
  let escaped = false;
  let inToken = false;

  for (const ch of input) {
    if (escaped) {
      current += ch;
      escaped = false;
      inToken = true;
      continue;
    }
    if (ch === '\\' && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (ch === quote) {
        quote = null;
      } else {
        current += ch;
      }
      inToken = true;
      continue;
    }
    if (ch === '"' || ch === "'") {
      quote = ch;
      inToken = true;
      continue;
    }
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      if (inToken) {
        args.push(current);
        current = '';
        inToken = false;
      }
      continue;
    }
    current += ch;
    inToken = true;
  }

  if (escaped) {
    current += '\\';
  }
  if (quote) {
    throw new ArgsParseError('Unterminated quote in launch arguments.');
  }
  if (inToken) {
    args.push(current);
  }
  return args;
}
