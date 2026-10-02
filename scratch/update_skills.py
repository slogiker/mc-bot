import os
import re

skills_dir = "/home/slogiker/.gemini/config/skills"
personas = [
    "franc-vrbancic", "marjan-ceh", "matevz-koren", "zoltan-sep", 
    "aljaz-seso", "zak-drofenik", "teller", "france-preseren", 
    "python", "tester"
]

delegation_section = """
# Delegation Protocol

To delegate to another specialist, invoke a 'self' type subagent and inject the target specialist's full SKILL.md content (read it with view_file first) as the subagent's initial prompt/role. Use 'research' type instead of 'self' when the delegated task is strictly read-only (no file writes, no shell commands) — research subagents are more restricted and that's safer when write access isn't needed.

Nesting is fully allowed: a self-clone running as one persona can itself invoke further self/research subagents (max platform-enforced depth: 10 levels) — so multi-layer delegation chains work, just always through self/research, never custom types.
"""

for persona in personas:
    file_path = os.path.join(skills_dir, persona, "SKILL.md")
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found")
        continue
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split frontmatter and body
    parts = content.split("---")
    if len(parts) < 3:
        print(f"Error: Invalid frontmatter in {file_path}")
        continue
        
    frontmatter = parts[1]
    body = "---".join(parts[2:])
    
    # 1. Remove subagents: block from frontmatter
    frontmatter = re.sub(r'subagents:\s*\n(\s+.*\n)*', '', frontmatter)
    
    # 2. Remove define_subagent and manage_subagents from tools list
    frontmatter = re.sub(r'\s*-\s+define_subagent\s*\n', '\n', frontmatter)
    frontmatter = re.sub(r'\s*-\s+manage_subagents\s*\n', '\n', frontmatter)
    
    # Cleanup any consecutive empty lines in frontmatter
    frontmatter = re.sub(r'\n\s*\n+', '\n', frontmatter)
    
    # 3. Add Delegation Protocol to body
    # Remove any existing "Delegation Protocol" or "Role & Delegation Protocol" section
    body = re.sub(r'# (Role & )?Delegation Protocol.*?(?=\n# |\Z)', '', body, flags=re.DOTALL)
    
    # Insert the new Delegation Protocol right after the first header (usually # Identity)
    first_header_match = re.search(r'(# Identity.*?\n)(?=\n# |\Z)', body, flags=re.DOTALL)
    if first_header_match:
        insert_pos = first_header_match.end()
        body = body[:insert_pos] + delegation_section + body[insert_pos:]
    else:
        body = delegation_section + body
        
    # Reassemble and write back
    new_content = f"---{frontmatter}---{body}"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Successfully updated {persona}")
