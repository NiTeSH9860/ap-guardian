"""
Splits long raw text into token-bounded chunks before sending to the extraction
model. Keeping extraction calls small is what keeps that stage cheap and fast —
see app/services/extraction.py and the model-routing rationale in the README.
"""
import tiktoken

_encoding = None


def _get_encoding():
    # Lazy-loaded: tiktoken fetches its BPE file on first use, so importing this
    # module never requires network access unless chunking is actually called.
    global _encoding
    if _encoding is None:
        _encoding = tiktoken.get_encoding("cl100k_base")
    return _encoding


def split_into_chunks(text: str, max_tokens: int = 1500) -> list[str]:
    if not text:
        return []

    encoding = _get_encoding()
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunk_tokens = tokens[i : i + max_tokens]
        chunks.append(encoding.decode(chunk_tokens))
    return chunks