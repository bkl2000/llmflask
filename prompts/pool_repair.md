The previous pool execution failed. Repair ONLY the failing script.

Error output:
{{error_output}}

Previous script ({{script_path}}):
{{script_content}}

Rules:
- Return ONLY the repaired script code. No explanations, no markdown, no other files.
- Fix the specific error shown above. Minimal change.
- Read from /pool/input. Write to /pool/output. Use absolute paths only.
- The script must remain idempotent after repair.
- Do not add new dependencies or new files.
