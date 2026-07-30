"""Code node sandbox (research.md §5) — layered defense for untrusted-ish Python
snippets: RestrictedPython compilation + a default-deny import allowlist, run in a
short-lived subprocess with resource.setrlimit CPU/memory/file caps, a minimal
environment (no secrets, no proxy vars), and a parent-enforced wall-clock timeout.
Threat model (Constitution VI): prevent accidents among ~5 trusted teammates, not
withstand a determined attacker with subprocess-exploit skills."""
