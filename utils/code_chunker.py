"""Code chunking utility for splitting large code files into manageable pieces."""

from typing import List


class CodeChunker:
    """Split large code into chunks while preserving logical structure."""

    @staticmethod
    def chunk_code(code: str, lines_per_chunk: int = 500) -> List[str]:
        """
        Split code into chunks by line count.

        Args:
            code: Full source code
            lines_per_chunk: Target lines per chunk (default 500)

        Returns:
            List of code chunks
        """
        lines = code.split('\n')
        chunks = []

        for i in range(0, len(lines), lines_per_chunk):
            chunk = '\n'.join(lines[i:i + lines_per_chunk])
            if chunk.strip():  # Only add non-empty chunks
                chunks.append(chunk)

        return chunks if chunks else [code]

    @staticmethod
    def get_chunk_count(code: str, lines_per_chunk: int = 500) -> int:
        """Get number of chunks without creating them."""
        lines = code.split('\n')
        return (len(lines) + lines_per_chunk - 1) // lines_per_chunk

    @staticmethod
    def needs_chunking(code: str, threshold: int = 2000) -> bool:
        """Check if code exceeds chunking threshold (default 2000 lines)."""
        return len(code.split('\n')) > threshold
