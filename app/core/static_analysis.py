import subprocess
import tempfile
import json


def _get_fix_suggestion(issue_type: str, explanation: str) -> str:
    """Provide context-aware fix suggestions based on issue type."""
    suggestions = {
        'hardcoded_sql_string': 'Use parameterized queries or prepared statements to safely handle user input.',
        'hardcoded_password_string': 'Move passwords to environment variables or a secure secret management system.',
        'assert_used': 'Use proper error handling and validation instead of assert statements.',
        'try_except_pass': 'Avoid bare except clauses; handle specific exceptions properly.',
        'exec_used': 'Avoid using exec() as it can execute arbitrary code. Use safer alternatives.',
        'eval_used': 'Avoid eval() as it poses security risks. Parse input safely instead.',
        'pickle_unsafe': 'Use JSON or other safe serialization formats instead of pickle.',
        'sql_injection': 'Use prepared statements or ORM frameworks to prevent SQL injection.',
        'hardcoded_bind_all': 'Bind to specific IP addresses instead of 0.0.0.0 in production.',
        'request_insecure_transport': 'Use HTTPS instead of HTTP for secure communication.',
        'subprocess_without_shell': 'Use shell=False when calling subprocess to avoid shell injection.',
    }
    
    for key, suggestion in suggestions.items():
        if key in issue_type.lower():
            return suggestion
    
    # Fallback: extract action from explanation
    if 'password' in explanation.lower():
        return 'Move sensitive data to environment variables or secure vaults.'
    elif 'sql' in explanation.lower() or 'query' in explanation.lower():
        return 'Use parameterized queries or prepared statements to prevent injection attacks.'
    elif 'overflow' in explanation.lower():
        return 'Add bounds checking and input validation to prevent overflow conditions.'
    elif 'buffer' in explanation.lower():
        return 'Use safe string handling functions and bounds checking.'
    elif 'null' in explanation.lower():
        return 'Add null checks before dereferencing pointers.'
    
    return 'Review the highlighted code and implement proper security controls.'


def run_bandit(code_text: str):
    """Run Bandit on a Python snippet by writing to temp file.

    Returns list of findings in the XAI output format.
    """
    findings = []
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.py', delete=False, encoding='utf-8'
    ) as f:
        f.write(code_text)
        fname = f.name

    try:
        # Run bandit in JSON output
        res = subprocess.run(
            ["bandit", "-r", fname, "-f", "json"],
            capture_output=True,
            text=True,
            timeout=20
        )
        out = res.stdout
        parsed = json.loads(out) if out else {}
        for item in parsed.get('results', []):
            test_name = item.get('test_name', 'bandit_issue')
            issue_text = item.get('issue_text', '')
            explanation = issue_text or f"Security issue detected by Bandit: {test_name}"
            
            # Create context-aware fix suggestion
            fix_suggestion = _get_fix_suggestion(test_name, explanation)
            
            findings.append({
                "issue": test_name,
                "severity": item.get('issue_severity', 'Medium'),
                "standard": "Bandit",
                "explanation": explanation,
                "highlighted_lines": (
                    [item.get('line_number')]
                    if item.get('line_number') else []
                ),
                "model_confidence": 1.0,
                "fix_suggestion": fix_suggestion
            })
    except Exception:
        pass
    return findings


def run_semgrep(code_text: str, lang: str = 'python'):
    findings = []
    with tempfile.NamedTemporaryFile(
        mode='w', suffix=f'.{lang}', delete=False, encoding='utf-8'
    ) as f:
        f.write(code_text)
        fname = f.name
    try:
        res = subprocess.run(
            ["semgrep", "--json", "-f", "p/ci", fname],
            capture_output=True,
            text=True,
            timeout=20
        )
        out = res.stdout
        parsed = json.loads(out) if out else {}
        for res_item in parsed.get('results', []):
            findings.append({
                "issue": res_item.get('check_id', 'semgrep_issue'),
                "severity": "High",
                "standard": "Semgrep",
                "explanation": res_item.get('extra', {}).get('message', ''),
                "highlighted_lines": (
                    [
                        loc.get('start', {}).get('line')
                        for loc in res_item.get('extra', {})
                        .get('lines', [])
                    ]
                    if res_item.get('extra', {}).get('lines') else []
                ),
                "model_confidence": 1.0,
                "fix_suggestion": "Follow semgrep rule guidance"
            })
    except Exception:
        pass
    return findings


def run_all(code_text: str, language: str = 'python'):
    findings = []
    if language.lower() == 'python':
        findings.extend(run_bandit(code_text))
    # Run semgrep for all languages if installed
    findings.extend(run_semgrep(code_text, language))

    # --- C Rule-based detection ---
    if language.lower() in ['c', 'cpp', 'c++']:
        import re
        lines = code_text.split('\n')
        checked_ptrs = set()
        for idx, line in enumerate(lines, 1):
            # Buffer Overflow: strcpy(
            if 'strcpy(' in line:
                findings.append({
                    'line': idx,
                    'risk_type': 'Buffer Overflow',
                    'severity': 'High',
                    'cwe': 'CWE-119',
                    'description': 'strcpy() does not check buffer bounds and can cause buffer overflow.',
                    'explanation': 'strcpy() copies a string without checking buffer size, which can lead to overflow attacks and arbitrary code execution.',
                    'fix_suggestion': 'Use strncpy() or strlcpy() with explicit buffer size limit instead of strcpy().',
                    'source': 'static',
                })
            # Integer Overflow: a * b or return a*b
            if re.search(r'\b\w+\s*\*\s*\w+\b', line) or re.search(r'return\s+\w+\s*\*\s*\w+', line):
                findings.append({
                    'line': idx,
                    'risk_type': 'Integer Overflow',
                    'severity': 'High',
                    'cwe': 'CWE-190',
                    'description': 'Multiplication may cause integer overflow without bounds checking.',
                    'explanation': 'Multiplication of two integers can overflow silently, causing incorrect calculations or memory allocation issues.',
                    'fix_suggestion': 'Add bounds checking before multiplication and use safe math libraries.',
                    'source': 'static',
                })
            # Unchecked Return Value: fopen()/fread() without NULL check
            if 'fopen(' in line or 'fread(' in line:
                # Check if next line checks for NULL
                next_line = lines[idx] if idx < len(lines) else ''
                if 'NULL' not in next_line and 'null' not in next_line:
                    findings.append({
                        'line': idx,
                        'risk_type': 'Unchecked Return Value',
                        'severity': 'Medium',
                        'cwe': 'CWE-252',
                        'description': 'Return value of fopen/fread not checked for NULL.',
                        'explanation': 'File operations may fail without indication. Not checking return values can lead to null pointer dereferences.',
                        'fix_suggestion': 'Always check if fopen() returns NULL before using the file pointer.',
                        'source': 'static',
                    })
            # Null Pointer Dereference: *ptr = or *ptr without null check
            ptr_deref = re.findall(r'\*(\w+)\s*[=;]', line)
            for ptr in ptr_deref:
                # Check if previous line checks for ptr != NULL
                prev_line = lines[idx-2] if idx > 1 else ''
                if f'{ptr} != NULL' not in prev_line and f'{ptr}==NULL' not in prev_line:
                    findings.append({
                        'line': idx,
                        'risk_type': 'Null Pointer Dereference',
                        'severity': 'High',
                        'cwe': 'CWE-476',
                        'description': f'Dereferencing pointer {ptr} without NULL check.',
                        'explanation': f'Pointer {ptr} is dereferenced without verifying it is not NULL, which can cause crashes or undefined behavior.',
                        'fix_suggestion': f'Add a null check: if ({ptr} != NULL) {{ /* use {ptr} */ }} before dereferencing.',
                        'source': 'static',
                    })
    return findings
