"""Fix YAML front matter escaping issues in scraped markdown files."""

import glob
import re


def fix_file(filepath: str) -> bool:
    with open(filepath, "r") as f:
        content = f.read()

    # Split front matter from body
    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = parts[1]
    body = parts[2]
    original_fm = fm

    if "\\" not in fm:
        return False

    # Process line by line to fix broken multiline quoted strings
    # and remove spurious backslash escapes from markdownify
    lines = fm.split("\n")
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]

        # Detect a key: "value that doesn't close its quote on this line
        match = re.match(r'^(\w[\w_]*): "(.*)', line)
        if match:
            key = match.group(1)
            rest = match.group(2)

            # Check if the quote is closed on this line
            # (ends with " but not with \")
            if rest.endswith('"') and not rest.endswith('\\"'):
                # Single-line quoted value — just clean up backslashes
                val = rest[:-1].replace("\\_", "_").replace("\\*", "*")
                val = val.replace("\\", "")
                new_lines.append(f'{key}: "{val}"')
            else:
                # Multiline: gather all lines until closing quote
                val_parts = [rest]
                i += 1
                while i < len(lines):
                    l = lines[i]
                    if l.rstrip().endswith('"') and not l.rstrip().endswith('\\"'):
                        val_parts.append(l.rstrip()[:-1])
                        break
                    val_parts.append(l)
                    i += 1
                val = "\n".join(val_parts)
                val = val.replace("\\_", "_").replace("\\*", "*").replace("\\", "")
                # Use YAML block scalar for multiline
                new_lines.append(f"{key}: |")
                for vl in val.split("\n"):
                    new_lines.append(f"  {vl}")
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
    for filepath in glob.glob("content/**/*.md", recursive=True):
        if fix_file(filepath):
            fixed += 1
            print(f"  Fixed: {filepath}")
    print(f"\nFixed {fixed} files total")


if __name__ == "__main__":
    main()
