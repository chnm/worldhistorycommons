"""
Comprehensive fix for YAML front matter quoting issues.
Converts all problematic quoted string values to YAML block scalars (|).
"""

import glob
import re

# Front matter keys that are single string values (not lists, not types)
STRING_KEYS = {
    "title", "source_citation", "credits", "how_to_cite",
    "website_authors", "reviewer", "reviewed_url", "pull_quote",
}


def fix_file(filepath: str) -> bool:
    with open(filepath, "r") as f:
        content = f.read()

    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]
    body = parts[2]
    original_fm = fm

    lines = fm.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this line is a key: "value" for one of our string keys
        match = re.match(r'^(\w[\w_]*): "(.*)', line)
        if match and match.group(1) in STRING_KEYS:
            key = match.group(1)
            rest = match.group(2)

            # Gather full value (may span multiple lines)
            # Find the true closing quote — one that isn't preceded by backslash
            full_val = rest
            closed = False

            # Check if closed on this line
            # A line ending with " that isn't \" closes the value
            if re.search(r'(?<!\\)"$', rest):
                full_val = rest[:-1]
                closed = True

            if not closed:
                # Multiline value — already handled by fix_yaml.py as block scalar
                # But if it's still broken, gather lines
                val_parts = [rest]
                i += 1
                while i < len(lines):
                    l = lines[i]
                    if re.search(r'(?<!\\)"$', l.rstrip()):
                        val_parts.append(l.rstrip()[:-1])
                        closed = True
                        break
                    val_parts.append(l)
                    i += 1
                full_val = "\n".join(val_parts)

            # Clean up the value
            full_val = full_val.replace('\\"', '"')

            # If the value contains quotes or newlines, use block scalar
            if '"' in full_val or "\n" in full_val:
                new_lines.append(f"{key}: |")
                for vl in full_val.split("\n"):
                    new_lines.append(f"  {vl}")
            else:
                new_lines.append(f'{key}: "{full_val}"')
        elif line.strip().startswith("- ") and line.strip().startswith('- "'):
            # List items — check for unescaped quotes inside
            # e.g., - "Imperial/ Colonial"  (these are fine)
            new_lines.append(line)
        else:
            new_lines.append(line)
        i += 1

    fm = "\n".join(new_lines)

    if fm != original_fm:
        with open(filepath, "w") as f:
            f.write("---" + fm + "---" + body)
        return True
    return False


def main():
    fixed = 0
    for filepath in sorted(glob.glob("content/**/*.md", recursive=True)):
        if fix_file(filepath):
            fixed += 1
    print(f"Fixed {fixed} files")


if __name__ == "__main__":
    main()
