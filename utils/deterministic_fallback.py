"""Deterministic rule-based fallback analyzer with 70+ vulnerability rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from models import GeminiResponsePayload


@dataclass(frozen=True)
class FallbackRule:
    issue: str
    severity: str
    cwe_id: str
    owasp_category: str
    fix: str
    patterns: tuple[str, ...]
    explanation: str
    confidence: float
    context_keywords: tuple[str, ...] = ()  # Optional context for filtering false positives


_SEVERITY_SCORE = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


class DeterministicFallbackAnalyzer:
    def __init__(self) -> None:
        self.rules: List[FallbackRule] = self._build_rules()

    def analyze(self, code: str, file_name: str = "snippet", language: str = "Unknown") -> GeminiResponsePayload:
        findings: List[Dict[str, Any]] = []
        lower_code = code.lower()

        for rule in self.rules:
            match_info = self._match_rule(rule, code, lower_code)
            if match_info is None:
                continue

            line_number, code_snippet = match_info
            findings.append(
                {
                    "id": f"fallback-{len(findings)+1}",
                    "line": line_number,
                    "risk_type": rule.issue,
                    "severity": rule.severity,
                    "cwe": rule.cwe_id,
                    "description": rule.explanation,
                    "category": rule.owasp_category,
                    "explanation": rule.explanation,
                    "exploit_scenario": rule.explanation,
                    "fix_suggestion": rule.fix,
                    "model_confidence": int(round(rule.confidence * 100)),
                    "codeSnippet": code_snippet,
                }
            )

        findings = self._dedupe_and_sort(findings)
        if findings:
            top = findings[0]
            return GeminiResponsePayload(
                vulnerability_detected=True,
                vulnerability_type="Multiple Vulnerabilities" if len(findings) > 1 else top.get("risk_type", ""),
                cwe_id=",".join(sorted({str(item.get("cwe", "")) for item in findings if item.get("cwe")})),
                owasp_category="Multiple Categories" if len(findings) > 1 else top.get("category", ""),
                risk_level=top.get("severity", "Medium"),
                confidence_score=min(0.99, max(0.55, sum(item["model_confidence"] for item in findings) / (100 * len(findings)))),
                explanation=" | ".join(item.get("explanation", "") for item in findings[:4]),
                recommended_fix="Review each finding and apply the suggested remediation.",
                findings=findings,
            )

        return GeminiResponsePayload(
            vulnerability_detected=False,
            vulnerability_type="",
            cwe_id="",
            owasp_category="",
            risk_level="Low",
            confidence_score=0.0,
            explanation="No vulnerabilities detected by deterministic rules.",
            recommended_fix="",
            findings=[],
        )

    def _match_rule(self, rule: FallbackRule, code: str, lower_code: str) -> Optional[tuple[int, str]]:
        """
        Match rule against code with context-aware filtering.
        If context_keywords specified, pattern must match AND at least one keyword must exist in same logical block.
        """
        for pattern in rule.patterns:
            match = re.search(pattern, code, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if match:
                # If rule has context requirements, validate context
                if rule.context_keywords:
                    if not self._has_context(code, match.start(), match.end(), rule.context_keywords):
                        continue
                
                line_number = code[: match.start()].count("\n") + 1
                snippet = self._build_snippet(code, match.start(), match.end())
                return line_number, snippet

            # Fallback to simple string search for non-regex patterns
            lower_pattern = pattern.lower()
            if lower_pattern in lower_code:
                # If rule has context requirements, validate context
                if rule.context_keywords:
                    index = lower_code.index(lower_pattern)
                    if not self._has_context(code, index, index + len(pattern), rule.context_keywords):
                        continue
                else:
                    index = lower_code.index(lower_pattern)
                
                line_number = lower_code[:index].count("\n") + 1
                snippet = self._build_snippet(code, index, index + len(pattern))
                return line_number, snippet

        return None

    @staticmethod
    def _has_context(code: str, match_start: int, match_end: int, context_keywords: tuple[str, ...]) -> bool:
        """
        Check if context keywords exist within a reasonable proximity to the match.
        Context is checked within ±500 characters around the match.
        """
        if not context_keywords:
            return True
        
        # Define search window around match (±500 chars)
        window_start = max(0, match_start - 500)
        window_end = min(len(code), match_end + 500)
        context_window = code[window_start:window_end].lower()
        
        # Return True if ANY context keyword is found in the window
        return any(keyword.lower() in context_window for keyword in context_keywords)

    @staticmethod
    def _build_snippet(code: str, start: int, end: int, window: int = 140) -> str:
        left = max(0, start - window)
        right = min(len(code), end + window)
        return " ".join(code[left:right].split())[:240]

    @staticmethod
    def _dedupe_and_sort(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[tuple[str, int, str], Dict[str, Any]] = {}
        for finding in findings:
            key = (
                str(finding.get("risk_type", "")).lower(),
                int(finding.get("line", 0)),
                str(finding.get("cwe", "")).lower(),
            )
            existing = merged.get(key)
            if existing is None:
                merged[key] = finding
                continue

            if _SEVERITY_SCORE.get(str(finding.get("severity", "Low")).title(), 0) > _SEVERITY_SCORE.get(
                str(existing.get("severity", "Low")).title(), 0
            ):
                existing["severity"] = finding.get("severity")
            if len(str(finding.get("description", ""))) > len(str(existing.get("description", ""))):
                existing["description"] = finding.get("description")
                existing["explanation"] = finding.get("explanation")
            if len(str(finding.get("fix_suggestion", ""))) > len(str(existing.get("fix_suggestion", ""))):
                existing["fix_suggestion"] = finding.get("fix_suggestion")
            if not existing.get("codeSnippet") and finding.get("codeSnippet"):
                existing["codeSnippet"] = finding.get("codeSnippet")

        return sorted(
            merged.values(),
            key=lambda item: (
                -_SEVERITY_SCORE.get(str(item.get("severity", "Low")).title(), 0),
                int(item.get("line", 0)),
                str(item.get("risk_type", "")).lower(),
            ),
        )

    @staticmethod
    def _build_rules() -> List[FallbackRule]:
        rules: List[FallbackRule] = []

        def add(issue: str, severity: str, cwe: str, owasp: str, fix: str, patterns: List[str], explanation: str, confidence: float, context: Optional[List[str]] = None):
            rules.append(
                FallbackRule(
                    issue=issue,
                    severity=severity,
                    cwe_id=cwe,
                    owasp_category=owasp,
                    fix=fix,
                    patterns=tuple(patterns),
                    explanation=explanation,
                    confidence=confidence,
                    context_keywords=tuple(context) if context else (),
                )
            )

        # SQL Injection (1-10)
        add("SQL Injection via String Concatenation", "Critical", "CWE-89", "A03:2021 - Injection", "Use parameterized queries or prepared statements.", [r"select\s+.*\+", r"insert\s+.*\+", r"update\s+.*\+", r"delete\s+.*\+"], "SQL query is built with string concatenation.", 0.96)
        add("SQL Injection via f-string", "Critical", "CWE-89", "A03:2021 - Injection", "Use bound parameters instead of f-strings.", [r"f[\"'].*select .*\{.*\}.*[\"']", r"f[\"'].*from .*\{.*\}.*[\"']"], "SQL query contains f-string interpolation.", 0.95)
        add("SQL Injection via format()", "Critical", "CWE-89", "A03:2021 - Injection", "Avoid format() in SQL. Use prepared statements.", [r"\.format\(.*select", r"\.format\(.*insert", r"\.format\(.*update"], "SQL query uses format() with untrusted input.", 0.94)
        add("SQL Injection via %-formatting", "Critical", "CWE-89", "A03:2021 - Injection", "Use parameterized queries and validate input.", [r"%\s*\w+.*select", r"%\s*\w+.*where"], "SQL query uses %-style formatting.", 0.93)
        add("SQL Injection in cursor.execute", "Critical", "CWE-89", "A03:2021 - Injection", "Pass parameters as a separate tuple/dict.", [r"cursor\.execute\(.*\+", r"execute\(.*request\.", r"executemany\(.*\+"], "Direct user input reaches cursor.execute.", 0.95)
        add("SQL Injection with request input", "Critical", "CWE-89", "A03:2021 - Injection", "Sanitize input and use bound parameters.", [r"request\.(args|form|json|values).*select", r"request\.(args|form|json|values).*insert"], "Request data is used directly in SQL.", 0.92)
        add("SQL Injection in dynamic table name", "High", "CWE-89", "A03:2021 - Injection", "Whitelist table names and use mapping.", [r"from\s+\{.*\}", r"table\s*=\s*request"], "Dynamic table or column name construction detected.", 0.89)
        add("SQL Injection via multiple statements", "Critical", "CWE-89", "A03:2021 - Injection", "Disable multi statements and use prepared statements.", [r";\s*drop\s+table", r";\s*delete\s+from", r";\s*update\s+"], "Multiple SQL statements are concatenated.", 0.91)
        add("Blind SQL Injection pattern", "High", "CWE-89", "A03:2021 - Injection", "Use prepared statements and consistent error handling.", [r"sleep\(\d+\)", r"or\s+1=1", r"and\s+1=1"], "Blind SQL injection style condition detected.", 0.88)
        add("Unsafely escaped SQL input", "High", "CWE-89", "A03:2021 - Injection", "Use ORM parameters or escaping utilities.", [r"escape\(.*request", r"sanitize_sql"], "Custom escaping detected in SQL path.", 0.87)

        # Command Injection (11-20)
        add("Command Injection via os.system", "Critical", "CWE-78", "A03:2021 - Injection", "Avoid shell execution; use safe APIs.", [r"os\.system\("], "os.system is used with dynamic input.", 0.97)
        add("Command Injection via os.popen", "Critical", "CWE-78", "A03:2021 - Injection", "Avoid popen for untrusted input.", [r"os\.popen\("], "os.popen is used with dynamic input.", 0.96)
        add("Command Injection via subprocess shell=True", "Critical", "CWE-78", "A03:2021 - Injection", "Set shell=False and pass args as a list.", [r"subprocess\.(run|call|Popen|check_output)\(.*shell\s*=\s*True"], "subprocess uses shell=True.", 0.96)
        add("Command Injection via dynamic shell command", "Critical", "CWE-78", "A03:2021 - Injection", "Use argument arrays and strict allowlists.", [r"bash\s+-c", r"sh\s+-c", r"cmd\s*=\s*.*\+"], "Dynamic shell command building detected.", 0.95)
        add("Unsafe eval usage", "Critical", "CWE-95", "A03:2021 - Injection", "Replace eval with safe parsing or explicit logic.", [r"eval\("], "eval is executed on potentially unsafe data.", 0.98)
        add("Unsafe exec usage", "Critical", "CWE-94", "A03:2021 - Injection", "Avoid exec; use explicit functions or AST parsing.", [r"exec\("], "exec is executed on potentially unsafe data.", 0.98)
        add("Command Injection through input concatenation", "High", "CWE-78", "A03:2021 - Injection", "Validate input and avoid shell strings.", [r"subprocess\..*\+.*request", r"os\.system\(.*request"], "User input is concatenated into a shell command.", 0.94)
        add("Command Injection through format strings", "High", "CWE-78", "A03:2021 - Injection", "Build commands with safe argument vectors.", [r"f[\"'].*(bash|sh|cmd).*\{.*\}"], "Shell command built with f-strings.", 0.93)
        add("Script execution with untrusted path", "High", "CWE-78", "A03:2021 - Injection", "Restrict executable paths and validate inputs.", [r"subprocess\..*script", r"python\s+.*\+"], "External script execution path detected.", 0.9)
        add("Command Injection via user-controlled file", "High", "CWE-78", "A03:2021 - Injection", "Do not pass user-controlled file names to shell.", [r"file_name.*\+.*subprocess", r"filename.*\+.*os\.system"], "User-controlled file data reaches shell execution.", 0.9)

        # File Handling (21-30) - With context-aware filtering
        add("Path Traversal via open()", "High", "CWE-22", "A05:2021 - Security Misconfiguration", "Normalize and whitelist paths before opening files.", [r"open\("], "open() uses user-controlled path input.", 0.9, context=["request", "input", "file_name", "path", "user"])
        add("Directory Traversal pattern", "High", "CWE-22", "A05:2021 - Security Misconfiguration", "Reject ../ and resolve against a safe base directory.", [r"\.\./", r"\.\.\\"], "Directory traversal sequence detected.", 0.91, context=["path", "file", "directory", "upload"])
        add("Absolute Path Exposure", "Medium", "CWE-22", "A05:2021 - Security Misconfiguration", "Restrict files to a safe root directory.", [r"/etc/passwd", r"/var/log", r"/root/"], "Potential sensitive absolute path access detected.", 0.8)
        add("Insecure Temporary File Usage", "Medium", "CWE-377", "A05:2021 - Security Misconfiguration", "Use secure temp file APIs and avoid delete=False when possible.", [r"tempfile\.(NamedTemporaryFile|mktemp)"], "Insecure temp file pattern detected.", 0.84, context=["delete", "password", "secret", "key"])
        add("File Overwrite Risk", "High", "CWE-73", "A05:2021 - Security Misconfiguration", "Validate output file paths and use safe file modes.", [r"open\(.*'w'", r"open\(.*\"w\""], "File is opened for writing without path safeguards.", 0.82, context=["request", "user", "input", "dynamic"])
        add("Unrestricted File Upload", "High", "CWE-434", "A05:2021 - Security Misconfiguration", "Validate file types and store outside web root.", [r"upload_file", r"request\.files", r"File\("], "Upload handling detected without clear restrictions.", 0.86, context=["request", "file", "upload"])
        add("Missing File Permission Controls", "Medium", "CWE-276", "A05:2021 - Security Misconfiguration", "Set restrictive file permissions explicitly.", [r"chmod\(.*0o777", r"os\.chmod\(.*0o777"], "World-writable permission pattern detected.", 0.85)
        add("Sensitive File Read", "High", "CWE-73", "A05:2021 - Security Misconfiguration", "Prevent access to secrets and config files.", [r"\.env", r"id_rsa", r"credentials\.json"], "Potential sensitive file access detected.", 0.81)
        add("Missing Path Validation", "High", "CWE-22", "A05:2021 - Security Misconfiguration", "Validate and canonicalize paths before use.", [r"os\.path\.join\(", r"Path\("], "User path input is joined without validation.", 0.88, context=["request", "input", "user", "dynamic"])
        add("Sandbox Bypass via file access", "Medium", "CWE-73", "A05:2021 - Security Misconfiguration", "Use sandboxing and safe file roots.", [r"read\(", r"write\("], "User-controlled file access pattern detected.", 0.77, context=["request", "input", "path"])

        # Authentication (31-40)
        add("Hardcoded Password", "Critical", "CWE-798", "A07:2021 - Identification and Authentication Failures", "Move secrets to environment variables or a secret manager.", [r"password\s*=\s*[\"'][^\"']+[\"']", r"passwd\s*=\s*[\"'][^\"']+[\"']"], "Hardcoded password detected.", 0.98)
        add("Hardcoded API Key", "Critical", "CWE-798", "A07:2021 - Identification and Authentication Failures", "Load API keys from secure environment variables.", [r"api[_-]?key\s*=\s*[\"'][^\"']+[\"']", r"secret\s*=\s*[\"'][^\"']+[\"']"], "Hardcoded API key or secret detected.", 0.98)
        add("Plain Text Password Storage", "Critical", "CWE-256", "A07:2021 - Identification and Authentication Failures", "Hash passwords with bcrypt, Argon2, or scrypt.", [r"store.*password.*plain", r"plaintext.*password", r"password.*in.*database"], "Plain text password storage pattern detected.", 0.95)
        add("No Password Hashing", "Critical", "CWE-916", "A07:2021 - Identification and Authentication Failures", "Hash passwords before storing or comparing.", [r"password.*==.*password", r"check_password.*==", r"user\.password"], "Password comparison without hashing detected.", 0.94)
        add("Weak Session Handling", "High", "CWE-384", "A07:2021 - Identification and Authentication Failures", "Use secure, random session identifiers with rotation.", [r"session_id\s*=\s*user", r"session\[.*\]", r"cookie.*session"], "Weak session management pattern detected.", 0.89)
        add("Missing Token Expiration", "High", "CWE-613", "A07:2021 - Identification and Authentication Failures", "Always include exp on JWTs and rotate tokens.", [r"jwt\.encode\(.*\)", r"access_token.*=", r"token.*valid.*forever"], "Token issuance without obvious expiry controls.", 0.88)
        add("Missing MFA", "Medium", "CWE-308", "A07:2021 - Identification and Authentication Failures", "Add MFA for privileged and sensitive actions.", [r"login.*password.*only", r"authenticate.*password"], "Single-factor authentication path detected.", 0.74)
        add("Admin Bypass Logic", "Critical", "CWE-287", "A07:2021 - Identification and Authentication Failures", "Enforce authorization checks server-side.", [r"if\s+admin\s*==\s*True", r"is_admin\s*=\s*True", r"role\s*==\s*['\"]admin['\"]"], "Potential admin bypass logic detected.", 0.93)
        add("Predictable Session ID", "High", "CWE-331", "A07:2021 - Identification and Authentication Failures", "Use cryptographically secure random values.", [r"random\.(randint|choice)", r"uuid\.uuid1", r"time\.time\(\).*token"], "Predictable session ID generation pattern detected.", 0.9)
        add("Weak Authentication Checks", "High", "CWE-287", "A07:2021 - Identification and Authentication Failures", "Centralize auth checks and require server validation.", [r"if\s+password", r"if\s+user.*authenticated"], "Weak authentication gate detected.", 0.84)

        # XSS (41-50)
        add("Reflected XSS via raw HTML", "Critical", "CWE-79", "A03:2021 - Injection", "Escape output and sanitize user content before rendering.", [r"innerHTML\s*=", r"document\.write\(", r"dangerouslySetInnerHTML"], "Raw HTML rendering of user content detected.", 0.97)
        add("Template Injection", "Critical", "CWE-79", "A03:2021 - Injection", "Use safe templating and escape variables.", [r"render_template_string", r"eval\(.*template", r"template.*\+.*request"], "Template injection pattern detected.", 0.95)
        add("Unsafe innerHTML usage", "High", "CWE-79", "A03:2021 - Injection", "Use textContent or sanitize HTML.", [r"\.innerHTML\s*=\s*.*request", r"\.innerHTML\s*=\s*.*input"], "innerHTML is assigned from user data.", 0.92)
        add("Unsafe query parameter rendering", "High", "CWE-79", "A03:2021 - Injection", "Escape query parameters before output.", [r"query_params?", r"request\.args.*render"], "Query parameter content is rendered directly.", 0.86)
        add("Unescaped response body", "High", "CWE-79", "A03:2021 - Injection", "Escape all user-controlled content in HTML responses.", [r"return .*<html", r"response\.write\(.*request"], "Potential HTML response injection detected.", 0.88)
        add("DOM-based XSS", "High", "CWE-79", "A03:2021 - Injection", "Use safe DOM APIs and sanitize inputs.", [r"location\.hash", r"location\.search", r"document\.location"], "DOM-based XSS sink/source pattern detected.", 0.89)
        add("Missing CSP headers", "Medium", "CWE-79", "A05:2021 - Security Misconfiguration", "Add a strict Content-Security-Policy.", [r"Content-Security-Policy", r"CSP"], "No CSP header handling detected.", 0.7)
        add("Unsafe templating raw output", "High", "CWE-79", "A03:2021 - Injection", "Escape templated variables by default.", [r"mark_safe", r"safe\s*:\s*true", r"{{\s*.*\|safe"], "Unsafe template raw-output control detected.", 0.9)
        add("Unfiltered user input in HTML", "High", "CWE-79", "A03:2021 - Injection", "Sanitize or encode user-controlled HTML.", [r"<div>\{.*request.*\}</div>"], "User data may be inserted into HTML directly.", 0.87)
        add("Script injection point", "Critical", "CWE-79", "A03:2021 - Injection", "Do not concatenate user data into script blocks.", [r"<script>.*request", r"javascript:\s*"], "Script injection sink detected.", 0.96)

        # Deserialization (51-55)
        add("Insecure pickle deserialization", "Critical", "CWE-502", "A08:2021 - Software and Data Integrity Failures", "Never unpickle untrusted data.", [r"pickle\.loads\("], "pickle.loads is used on input data.", 0.98)
        add("Unsafe YAML load", "Critical", "CWE-502", "A08:2021 - Software and Data Integrity Failures", "Use yaml.safe_load.", [r"yaml\.load\("], "yaml.load is used without safe loader.", 0.97)
        add("Unsafe eval deserialization", "Critical", "CWE-94", "A03:2021 - Injection", "Replace eval with structured parsing.", [r"eval\(.*input", r"eval\(.*request"], "eval is used on external input.", 0.98)
        add("Unsafe exec deserialization", "Critical", "CWE-94", "A03:2021 - Injection", "Avoid exec on user-controlled data.", [r"exec\(.*input", r"exec\(.*request"], "exec is used on external input.", 0.98)
        add("Unsafe JSON parsing callback", "Medium", "CWE-20", "A05:2021 - Security Misconfiguration", "Validate schema before processing JSON.", [r"json\.loads\(.*request", r"object_hook="], "Potential unsafe JSON parsing path detected.", 0.75)

        # Weak randomness (56-60) - Now with context-aware filtering
        add("Weak Randomness for Tokens", "High", "CWE-338", "A02:2021 - Cryptographic Failures", "Use secrets.token_urlsafe or os.urandom.", [r"random\.randint\(", r"random\.choice\("], "random module is used for token generation.", 0.9, context=["token", "auth", "secret", "key", "password"])
        add("Predictable Random Seed", "High", "CWE-330", "A02:2021 - Cryptographic Failures", "Use secure RNG and avoid predictable seeds.", [r"random\.seed\(.*time", r"seed\(time\.time\("], "Predictable RNG seed detected.", 0.89)
        add("Non-cryptographic UUID usage", "Medium", "CWE-330", "A02:2021 - Cryptographic Failures", "Use uuid4 for random identifiers.", [r"uuid\.uuid1\("], "uuid1 may reveal timestamp/MAC information.", 0.73, context=["token", "session", "identifier", "auth"])
        add("Timestamp-based token", "High", "CWE-330", "A02:2021 - Cryptographic Failures", "Use cryptographically secure random tokens.", [r"time\.time\(\).*token", r"datetime\.now\(\).*token"], "Timestamp-based token pattern detected.", 0.88)
        add("Repeated token pattern", "Medium", "CWE-330", "A02:2021 - Cryptographic Failures", "Generate unique cryptographic tokens.", [r"token\s*=\s*str\(random", r"token\s*=\s*str\(uuid\.uuid1"], "Predictable token generation pattern detected.", 0.78)

        # Config issues (61-65)
        add("Debug Mode Enabled", "High", "CWE-489", "A05:2021 - Security Misconfiguration", "Disable debug mode in production.", [r"debug\s*=\s*True", r"app\.run\(.*debug\s*=\s*True"], "Debug mode is enabled.", 0.92)
        add("Verbose Error Exposure", "Medium", "CWE-209", "A05:2021 - Security Misconfiguration", "Use generic error messages for clients.", [r"print\(e\)", r"return .*traceback", r"traceback\.format_exc\("], "Verbose error output exposed.", 0.78)
        add("Default Configuration Values", "Medium", "CWE-16", "A05:2021 - Security Misconfiguration", "Override defaults with secure configuration.", [r"default_password", r"default_secret", r"DEFAULT_"], "Default security-sensitive config detected.", 0.81)
        add("Exposed Environment Variables", "High", "CWE-200", "A05:2021 - Security Misconfiguration", "Do not return secrets or env values in responses.", [r"os\.environ", r"ENV\[", r"getenv\("], "Environment value exposure pattern detected.", 0.84)
        add("Insecure Host Binding", "Low", "CWE-284", "A05:2021 - Security Misconfiguration", "Bind only to trusted interfaces in production.", [r"host\s*=\s*['\"]0\.0\.0\.0['\"]"], "Service binds to all interfaces.", 0.62)

        # API & Network (66-70)
        add("Plain HTTP Usage", "High", "CWE-319", "A02:2021 - Cryptographic Failures", "Use HTTPS for all sensitive network traffic.", [r"http://"], "Plain HTTP endpoint usage detected.", 0.9)
        add("TLS Verification Disabled", "Critical", "CWE-295", "A02:2021 - Cryptographic Failures", "Keep certificate verification enabled.", [r"verify\s*=\s*False", r"ssl\.CERT_NONE", r"create_unverified_context"], "TLS verification is disabled.", 0.97)
        add("Open CORS Policy", "Medium", "CWE-942", "A05:2021 - Security Misconfiguration", "Restrict allowed origins to trusted domains.", [r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]", r"CORS.*\*"], "CORS policy allows any origin.", 0.8)
        add("Open Network Endpoint", "Medium", "CWE-306", "A01:2021 - Broken Access Control", "Require authentication and authorization.", [r"@app\.route", r"@router\.(get|post|put|delete)"], "Public endpoint pattern detected; verify auth controls.", 0.7)
        add("Missing Rate Limiting", "Medium", "CWE-770", "A04:2021 - Insecure Design", "Add request throttling and per-user limits.", [r"no rate limiting", r"rate.?limit"], "No rate limiting control detected in route path.", 0.72)

        # Extra rules to exceed 70
        add("Missing Input Sanitization", "High", "CWE-20", "A03:2021 - Injection", "Validate and sanitize all external input.", [r"request\.(args|json|form)"], "Request input is used in a sensitive context.", 0.85)
        add("Unsafe Regex from User Input", "High", "CWE-730", "A03:2021 - Injection", "Use safe regex building and validate patterns.", [r"re\.compile\(.*request", r"re\.search\(.*request"], "User input is used to build regular expressions.", 0.84)
        add("Open Redirect", "High", "CWE-601", "A01:2021 - Broken Access Control", "Allow redirects only to whitelisted targets.", [r"redirect\(.*request", r"return_url", r"next=.*request"], "Potential open redirect detected.", 0.88)
        add("CSRF Missing", "Medium", "CWE-352", "A01:2021 - Broken Access Control", "Add CSRF protection for state-changing requests.", [r"@app\.route\(.*POST", r"@router\.post"], "State-changing route detected; verify CSRF controls.", 0.75)
        add("Missing Authorization Check", "Critical", "CWE-862", "A01:2021 - Broken Access Control", "Enforce authorization before sensitive actions.", [r"if\s+user\s*:", r"if\s+authenticated\s*:", r"return\s+True"], "Potential missing authorization check.", 0.9)
        add("Sensitive Data in Logs", "High", "CWE-532", "A09:2021 - Security Logging and Monitoring Failures", "Redact secrets before logging.", [r"logger\.(info|debug|error)\(.*password", r"print\(.*token"], "Sensitive value may be logged.", 0.91)
        add("Excessive Privilege", "High", "CWE-269", "A01:2021 - Broken Access Control", "Use least privilege and role checks.", [r"is_admin\s*=\s*True", r"role\s*=\s*['\"]admin['\"]"], "Potential excessive privilege pattern detected.", 0.86)
        add("Hardcoded Secret File", "Critical", "CWE-798", "A05:2021 - Security Misconfiguration", "Move secrets out of source control.", [r"\.env", r"secret_key", r"api_secret"], "Secret-like values found in source code.", 0.96)
        add("Weak Hash for Secrets", "High", "CWE-327", "A02:2021 - Cryptographic Failures", "Use SHA-256+ or password hashing algorithms.", [r"md5\(", r"sha1\(", r"hashlib\.md5", r"hashlib\.sha1"], "Weak cryptographic hash function detected.", 0.9)
        add("Insecure Random Password Reset", "High", "CWE-338", "A02:2021 - Cryptographic Failures", "Use cryptographically secure tokens for reset codes.", [r"reset.*random", r"otp.*random", r"code.*random"], "Password reset flow uses weak randomness.", 0.84)
        add("Unsafe XML Parsing", "High", "CWE-611", "A05:2021 - Security Misconfiguration", "Disable external entities and use secure XML parsers.", [r"xml\.parse", r"ElementTree\.parse", r"lxml"], "XML parsing path may be unsafe.", 0.8)
        add("Unsafe Deserialization via marshal", "Critical", "CWE-502", "A08:2021 - Software and Data Integrity Failures", "Never deserialize untrusted marshal data.", [r"marshal\.loads\("], "marshal.loads is used.", 0.97)
        add("Unsafe URL Fetch", "Medium", "CWE-918", "A10:2021 - Server-Side Request Forgery", "Validate outbound URLs and restrict hosts.", [r"requests\.(get|post)\(.*request", r"urlopen\(.*request"], "Potential SSRF pattern detected.", 0.79)
        add("SSRF via user-controlled URL", "Critical", "CWE-918", "A10:2021 - Server-Side Request Forgery", "Whitelist allowed hosts and block internal ranges.", [r"request\.args.*url", r"request\.json.*url"], "User-controlled URL may be fetched.", 0.95)
        add("Command Path Injection", "High", "CWE-78", "A03:2021 - Injection", "Use fixed command paths and safe args.", [r"/bin/sh", r"/bin/bash", r"cmd\.exe"], "Command path execution surface detected.", 0.87)
        add("Unsafe Path Join", "High", "CWE-22", "A05:2021 - Security Misconfiguration", "Resolve paths and enforce base directory checks.", [r"os\.path\.join\(.*request", r"Path\(.*request"], "Path join with request data detected.", 0.89)
        add("Unbounded File Read", "Medium", "CWE-400", "A05:2021 - Security Misconfiguration", "Limit file sizes and stream reads.", [r"read\(\)", r"readlines\(\)"], "Potential unbounded file read detected.", 0.7)
        add("Missing HTTPS Enforcement", "High", "CWE-319", "A02:2021 - Cryptographic Failures", "Redirect to HTTPS and reject plaintext.", [r"http://", r"ssl=False"], "HTTPS enforcement is not visible.", 0.9)
        add("Insufficient Logging for Security Events", "Low", "CWE-778", "A09:2021 - Security Logging and Monitoring Failures", "Log auth failures and privilege changes.", [r"login", r"auth"], "Security logging coverage may be insufficient.", 0.6)
        add("Weak Secret Derivation", "High", "CWE-327", "A02:2021 - Cryptographic Failures", "Use a modern KDF such as Argon2 or bcrypt.", [r"hashlib\.(md5|sha1)", r"pbkdf2"], "Weak secret derivation pattern detected.", 0.88)

        return rules
