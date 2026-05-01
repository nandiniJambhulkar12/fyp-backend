import hashlib
import re
from typing import Optional

from fastapi import HTTPException, UploadFile

from config import Settings
from language_detector import detect_language, is_supported_extension
from models import ParsedCode


CONTROL_CHARACTERS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CODE_SIGNAL_RE = re.compile(
    r"(def\s+\w+\(|class\s+\w+|function\s+\w+\(|#include\s+<|public\s+class|SELECT\s+.+FROM|#!/bin/(ba|z|k)?sh|package\s+main|fn\s+\w+\()",
    re.IGNORECASE | re.MULTILINE,
)
LANGUAGE_SIGNALS = {
    "Python": ("def ", "import ", "from ", "print(", "if ", "for "),
    "Java": ("public class", "System.out", "package ", "import java"),
    "JavaScript": ("function ", "const ", "let ", "console.", "=>"),
    "C": ("#include", "printf(", "scanf(", "int main"),
    "C++": ("#include", "std::", "cout <<", "int main"),
    "C#": ("using System", "namespace ", "Console.Write", "public class"),
    "Go": ("package main", "func ", "fmt."),
    "Rust": ("fn ", "println!", "let mut "),
    "PHP": ("<?php", "echo ", "$_GET", "$_POST"),
    "Ruby": ("def ", "puts ", "class ", "end"),
    "SQL": ("SELECT ", "INSERT ", "UPDATE ", "DELETE "),
    "Shell": ("#!/bin/", "echo ", "if [", "then"),
    "TypeScript": ("interface ", "type ", ": string", ": number", "=>"),
}


async def parse_code_input(
    file: Optional[UploadFile],
    code: Optional[str],
    declared_language: Optional[str],
    settings: Settings,
) -> ParsedCode:
    file_name = "snippet.txt"
    code_content = ""

    if file is not None:
        file_name = file.filename or file_name
        raw_bytes = await file.read()
        if len(raw_bytes) > settings.max_file_size_bytes:
            raise HTTPException(status_code=413, detail="File exceeds the 1 MB limit")
        if not raw_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if not is_supported_extension(file_name) and not declared_language:
            raise HTTPException(status_code=415, detail="Unsupported file type")
        code_content = raw_bytes.decode("utf-8", errors="ignore")
    else:
        code_content = code or ""

    sanitized_code = sanitize_code_content(code_content)
    if not sanitized_code.strip():
        raise HTTPException(status_code=400, detail="Code content is empty after sanitization")

    language = detect_language(file_name=file_name, declared_language=declared_language, code_content=sanitized_code)
    if language == "Unknown":
        raise HTTPException(status_code=415, detail="Unsupported or undetectable programming language")
    if file is None:
        file_name = build_virtual_filename(language)

    if not looks_like_code(sanitized_code, language):
        raise HTTPException(status_code=415, detail="Input does not appear to be source code")

    truncated_code = sanitized_code[: settings.max_code_characters]
    code_hash = hashlib.sha256(sanitized_code.encode("utf-8")).hexdigest()
    return ParsedCode(
        file_name=file_name,
        language=language,
        code_content=sanitized_code,
        truncated_code=truncated_code,
        code_hash=code_hash,
    )


def sanitize_code_content(code_content: str) -> str:
    normalized = code_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = CONTROL_CHARACTERS_RE.sub("", normalized)
    return normalized.strip()


def looks_like_code(code_content: str, language: str) -> bool:
    if CODE_SIGNAL_RE.search(code_content):
        return True

    for signal in LANGUAGE_SIGNALS.get(language, ()):
        if signal in code_content:
            return True

    signal_count = sum(code_content.count(token) for token in ("{", "}", "(", ")", ";", "=>", "::", "==", "!=", "[]"))
    alnum_ratio = sum(char.isalnum() for char in code_content) / max(len(code_content), 1)
    return signal_count >= 2 and alnum_ratio >= 0.25


def build_virtual_filename(language: str) -> str:
    extension_map = {
        "Python": ".py",
        "Java": ".java",
        "JavaScript": ".js",
        "C": ".c",
        "C++": ".cpp",
        "C#": ".cs",
        "Go": ".go",
        "Rust": ".rs",
        "PHP": ".php",
        "Ruby": ".rb",
        "SQL": ".sql",
        "Shell": ".sh",
        "TypeScript": ".ts",
    }
    return f"snippet{extension_map.get(language, '.txt')}"