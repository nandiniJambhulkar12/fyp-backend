import os
import re
from typing import Optional


EXTENSION_LANGUAGE_MAP = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".rb": "Ruby",
    ".sql": "SQL",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ksh": "Shell",
    ".ts": "TypeScript",
}

LANGUAGE_ALIASES = {
    "python": "Python",
    "py": "Python",
    "java": "Java",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "c": "C",
    "c++": "C++",
    "cpp": "C++",
    "cxx": "C++",
    "c#": "C#",
    "cs": "C#",
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "rs": "Rust",
    "php": "PHP",
    "ruby": "Ruby",
    "rb": "Ruby",
    "sql": "SQL",
    "shell": "Shell",
    "bash": "Shell",
    "zsh": "Shell",
    "sh": "Shell",
    "typescript": "TypeScript",
    "ts": "TypeScript",
}

HEURISTIC_PATTERNS = (
    (re.compile(r"(^\s*def\s+\w+\(|import\s+\w+|from\s+\w+\s+import\s+)", re.MULTILINE), "Python"),
    (re.compile(r"(public\s+class\s+\w+|System\.out\.println|package\s+[\w.]+;)", re.MULTILINE), "Java"),
    (re.compile(r"(console\.log|function\s+\w+\(|const\s+\w+\s*=|let\s+\w+\s*=)", re.MULTILINE), "JavaScript"),
    (re.compile(r"(#include\s+<\w+>|printf\s*\(|scanf\s*\()", re.MULTILINE), "C"),
    (re.compile(r"(std::\w+|#include\s+<iostream>|using\s+namespace\s+std)", re.MULTILINE), "C++"),
    (re.compile(r"(using\s+System;|namespace\s+\w+\s*\{|Console\.WriteLine)", re.MULTILINE), "C#"),
    (re.compile(r"(func\s+\w+\(|package\s+main|fmt\.Println)", re.MULTILINE), "Go"),
    (re.compile(r"(fn\s+\w+\(|println!\s*\(|use\s+std::)", re.MULTILINE), "Rust"),
    (re.compile(r"(<\?php|->\w+\(|echo\s+\$)", re.MULTILINE), "PHP"),
    (re.compile(r"(puts\s+['\"]|def\s+\w+\s*$|end\s*$)", re.MULTILINE), "Ruby"),
    (re.compile(r"(SELECT\s+.+\s+FROM|INSERT\s+INTO|UPDATE\s+\w+\s+SET)", re.IGNORECASE | re.MULTILINE), "SQL"),
    (re.compile(r"(^#!/bin/(ba|z|k)?sh|\becho\b|\bfi\b|\bthen\b)", re.MULTILINE), "Shell"),
    (re.compile(r"(interface\s+\w+\s*\{|type\s+\w+\s*=|: string\b|: number\b)", re.MULTILINE), "TypeScript"),
)


def is_supported_extension(filename: str) -> bool:
    _, extension = os.path.splitext(filename or "")
    return extension.lower() in EXTENSION_LANGUAGE_MAP


def normalize_language(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return LANGUAGE_ALIASES.get(value.strip().lower())


def detect_language(file_name: str, declared_language: Optional[str], code_content: str) -> str:
    normalized = normalize_language(declared_language)
    if normalized:
        return normalized

    _, extension = os.path.splitext(file_name or "")
    extension_language = EXTENSION_LANGUAGE_MAP.get(extension.lower())
    if extension_language:
        return extension_language

    for pattern, language in HEURISTIC_PATTERNS:
        if pattern.search(code_content):
            return language

    return "Unknown"