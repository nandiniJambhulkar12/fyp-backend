# 📖 Quick Reference Guide - Deterministic Fallback Analyzer

## 🎯 What Is Context-Aware Filtering?

It's a mechanism to **reduce false positives** by requiring patterns to match **AND** have relevant keywords nearby.

### Example: Weak Randomness Detection

**Without Context (Old Approach):**

```python
# Any random.randint() gets flagged
score = random.randint(1, 100)  # ❌ False Positive - Game code, not security-sensitive
```

**With Context (New Approach):**

```python
# Only random.randint() near security keywords gets flagged
score = random.randint(1, 100)  # ✅ NOT flagged - "token", "auth" keywords not nearby
token = random.randint(100000, 999999)  # ❌ Flagged - "token" keyword found nearby!
```

---

## 🛠️ How to Use Context in Rules

### Basic Syntax

```python
add(
    issue="Rule Name",
    severity="High",
    cwe="CWE-XXX",
    owasp="A03:2021 - ...",
    fix="How to fix this",
    patterns=[r"pattern1", r"pattern2"],
    explanation="Why this is bad",
    confidence=0.95,
    context=["keyword1", "keyword2"]  # ← Optional context filter
)
```

### Example 1: Token Generation

```python
add(
    issue="Weak Randomness for Tokens",
    severity="High",
    cwe="CWE-338",
    owasp="A02:2021 - Cryptographic Failures",
    fix="Use secrets.token_urlsafe() instead",
    patterns=[r"random\.randint\(", r"random\.choice\("],
    explanation="random module used for token generation",
    confidence=0.90,
    context=["token", "auth", "secret", "key", "password"]  # Only flag if these keywords nearby
)
```

### Example 2: File Path Handling

```python
add(
    issue="Path Traversal via open()",
    severity="High",
    cwe="CWE-22",
    owasp="A05:2021 - Security Misconfiguration",
    fix="Normalize and whitelist paths before opening",
    patterns=[r"open\("],
    explanation="open() may use user-controlled path",
    confidence=0.90,
    context=["request", "input", "file_name", "path", "user"]
)
```

### Example 3: No Context Required (Always Flag)

```python
add(
    issue="Insecure pickle deserialization",
    severity="Critical",
    cwe="CWE-502",
    owasp="A08:2021 - Software and Data Integrity Failures",
    fix="Never unpickle untrusted data",
    patterns=[r"pickle\.loads\("],
    explanation="pickle.loads on external input",
    confidence=0.98
    # No context parameter = always flags
)
```

---

## 🔍 How Context Matching Works

### The Algorithm

```
FOR EACH rule:
    FOR EACH pattern in rule.patterns:
        IF pattern matches code:
            IF rule has context_keywords:
                IF any keyword within ±500 chars of match:
                    REPORT finding ✅
                ELSE:
                    SKIP this pattern ⏭️
            ELSE:
                REPORT finding ✅ (always)
```

### Context Window

- **Distance:** ±500 characters around the match
- **Speed:** O(1) operation, negligible overhead
- **Scope:** Reasonable for most code patterns

### Example Context Match

```
Code:
    def generate_auth_token():
        token = random.randint(100000, 999999)
                ↑ Pattern matches here

    Context window:
    [......generate_auth_token.....]  (±500 chars)
    └─ Contains "token" keyword ✅
    └─ Finding REPORTED ✅
```

---

## 📊 Current Context-Aware Rules

### Weak Randomness (4 rules)

```python
context = ["token", "auth", "secret", "key", "password"]
```

- `random.randint()` - Flags if in security context
- `random.choice()` - Flags if in security context
- `uuid.uuid1()` - Flags if for identifiers/sessions
- `time.time()` tokens - Always flags (high severity)

### File Operations (6 rules)

```python
context = ["request", "input", "file_name", "path", "user"]  # for most
context = ["delete", "password", "secret", "key"]  # for temp files
```

- `open()` - Requires user/request context
- `os.path.join()` - Requires user/request context
- `tempfile` - Requires sensitive data context
- Path traversal patterns - Requires file context

### Other Context-Enhanced Rules

- UUID usage for identifiers
- File uploads
- Temporary files with sensitive data
- Path validation
- Sandbox bypass

---

## ✅ Best Practices

### DO ✓

```python
# 1. Use context for patterns that have many false positives
add(..., patterns=[r"random\."], context=["token", "auth"])

# 2. Be specific with keywords - "token" > "rand"
context = ["api_token", "session_token"]  # GOOD

# 3. Test with real code samples before adding rules
# Use test_deterministic_improvements.py

# 4. Document WHY context is needed
# "random.randint for games vs tokens has different risk levels"

# 5. Keep patterns simple, let context do filtering
patterns = [r"random\.randint\("]  # Pattern is broad
context = ["token", "secret"]       # Context narrows it down
```

### DON'T ✗

```python
# 1. Don't make patterns TOO specific to avoid context
# ✗ patterns=[r"random\.randint\(.*token"]  AVOID - pattern too specific
# ✓ patterns=[r"random\.randint\("], context=["token"]  PREFER - clean separation

# 2. Don't forget context for high false-positive patterns
# ✗ add("Weak Randomness", ..., patterns=[r"random\."])  No context = lots of FP
# ✓ add("Weak Randomness", ..., patterns=[r"random\."], context=["token"])

# 3. Don't use vague keywords
# ✗ context=["use"]  Too generic
# ✓ context=["token", "password", "api_key"]  Specific

# 4. Don't add context to always-bad patterns
# ✗ add("pickle.loads()", ..., context=["data"])  Unnecessary
# ✓ add("pickle.loads()", ...)  Always bad
```

---

## 🧪 Testing Your Changes

### Step 1: Add Rule

```python
add(
    issue="My New Rule",
    severity="Medium",
    cwe="CWE-123",
    owasp="A01:2021 - ...",
    fix="Fix suggestion",
    patterns=[r"my_pattern"],
    explanation="Why this is bad",
    confidence=0.85,
    context=["optional", "keywords"]
)
```

### Step 2: Create Test Cases

```python
# test_my_rule.py

analyzer = DeterministicFallbackAnalyzer()

# Test 1: False positive case
code_benign = """
    # Code that matches pattern but NOT vulnerable
    my_pattern_in_safe_context()
"""
result = analyzer.analyze(code_benign)
assert len(result.findings) == 0, "Should not flag safe code"

# Test 2: True positive case
code_vulnerable = """
    # Code that matches pattern AND is vulnerable
    user_input = request.args.get('data')
    process_with_my_pattern(user_input)
"""
result = analyzer.analyze(code_vulnerable)
assert len(result.findings) > 0, "Should flag vulnerable code"
```

### Step 3: Run Tests

```bash
python3 test_deterministic_improvements.py
```

### Step 4: Verify Confidence Scores

```python
# Check accuracy in edge cases
print(f"Finding confidence: {result.findings[0]['model_confidence']}%")
# 90-98% = High confidence (use this)
# 70-89% = Medium confidence (use with context)
# <70% = Low confidence (reconsider rule)
```

---

## 📈 Metrics & Monitoring

### Track These

```python
# Confidence scores
finding['model_confidence']  # 0-100%, higher is better

# Severity levels
finding['severity']  # Critical, High, Medium, Low

# Detection accuracy
total_findings / code_lines  # Should be <1% for clean code

# False positive rate
false_positives / total_findings  # Target: <25%
```

### Adjust If Needed

```python
# Too many false positives? → Add context keywords
# Too few findings? → Broaden pattern or remove context
# Wrong severity? → Adjust severity level
# Low confidence? → Add more pattern variations or reconsider rule
```

---

## 🔄 Integration Example

### Using in Your Application

```python
from utils.deterministic_fallback import DeterministicFallbackAnalyzer

def scan_code(code: str) -> dict:
    analyzer = DeterministicFallbackAnalyzer()

    # Analyze
    result = analyzer.analyze(code, file_name="code.py", language="python")

    # Extract findings
    findings = []
    for finding in result.findings:
        findings.append({
            "line": finding['line'],
            "type": finding['risk_type'],
            "severity": finding['severity'],
            "confidence": finding['model_confidence'],
            "fix": finding['fix_suggestion']
        })

    return {
        "total_issues": len(findings),
        "risk_level": result.risk_level,
        "findings": findings
    }
```

---

## 🎓 FAQ

**Q: How many keywords should I use in context?**
A: 3-6 keywords is ideal. Fewer → too broad, More → too narrow.

**Q: Can I use regex in keywords?**
A: No, keywords are simple substring matches (case-insensitive).

**Q: What if pattern rarely has false positives?**
A: Skip context parameter. If severity is CRITICAL, definitely skip context.

**Q: How do I debug why a finding wasn't reported?**
A: Add print statements to `_match_rule()` or `_has_context()`.

**Q: Can I change the ±500 character window?**
A: Yes, edit `_has_context()` method. Search for `window_start = max(0, match_start - 500)`.

**Q: Should I use context for CRITICAL severity rules?**
A: Only if you have many false positives. Most CRITICAL rules should always flag.

---

## 🚀 Next Steps

1. **Review Current Rules** - See which have context already
2. **Add More Context** - Find patterns with high false positive rates
3. **Test Changes** - Run test suite after modifications
4. **Monitor Performance** - Track confidence scores in production
5. **Iterate** - Refine based on real-world results

---

**Last Updated:** May 1, 2026
**Version:** 2.0 - Context-Aware Edition
**Status:** ✅ Production Ready
