def suggest_fix(rule_or_source: str, code_text: str):
    # Minimal recommender mapping common patterns to suggestions.
    if 'password' in code_text.lower() or 'passwd' in code_text.lower():
        return (
            'Use environment variables or a secrets manager; '
            'do not hardcode credentials.'
        )
    if rule_or_source == 'ml':
        return (
            'Review highlighted lines and apply secure coding '
            'practices; consider input validation and proper '
            'error handling.'
        )
    return 'Apply secure coding best practices; consult compliance rules.'
