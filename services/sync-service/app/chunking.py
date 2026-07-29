def build_chunks(items: list[str], size: int = 100) -> list[list[str]]:
    if size < 1:
        raise ValueError("Chunk size must be positive")
    unique = list(dict.fromkeys(items))
    return [unique[index:index + size] for index in range(0, len(unique), size)]
