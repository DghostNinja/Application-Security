# Custom Semgrep rules (OSS, no token required)
#
# These rules fill the coverage gap left by Semgrep's free OSS packs. They are
# written and maintained by this team, and run in every security-scan workflow
# run - with or without a SEMGREP_APP_TOKEN.
#
# How they are used:
#   The security-scan workflow always runs:
#       semgrep scan --config .semgrep/custom/ ...
#   When a SEMGREP_APP_TOKEN is present, Pro rules run IN ADDITION. If the
#   token is absent, or Semgrep hits the free-tier usage limit, the workflow
#   automatically falls back to OSS packs + these custom rules (never a silent
#   failure - the report states which mode ran).
#
# How to maintain / add rules:
#   * Each rule has: a unique `id`, `severity`, `languages`, `message` and a
#     `pattern` (or taint sources/sinks/sanitizers).
#   * Keep rules specific to avoid false positives. When you find a real bug,
#     write the smallest rule that catches it and test it:
#
#       semgrep scan --config .semgrep/custom/ --validate
#       semgrep scan --config .semgrep/custom/ .
#
#   * Prefer taint mode (`mode: taint`) for anything involving user input
#     reaching a dangerous sink (file, network, process).
#   * `pattern-sanitizers` is how you teach Semgrep that a value is safe
#     (e.g. Path.GetFileName, containment checks). Update sanitizers when the
#     codebase adds new validation helpers.
#   * Rules should be portable: they must not reference this repo's files or
#     paths, so the same .semgrep/ folder works in every repo.
#   * Severity guide:
#       ERROR   - exploitable, must fix (reported by default)
#       WARNING - best practice, review (reported only if severity widened)
#
# Rule inventory:
#   csharp-path-traversal-write/read/delete : request data -> file IO
#   csharp-ssrf                            : request data -> outbound HTTP URL
#   csharp-command-injection               : request data -> Process.Start
#   csharp-insecure-crypto-password        : MD5/SHA1 on password data
#   csharp-hardcoded-secret                : secrets in string literals
