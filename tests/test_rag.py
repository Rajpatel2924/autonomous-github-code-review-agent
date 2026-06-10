from rag.indexer import chunk_code, language_for_path


def test_chunk_code_adds_metadata() -> None:
    content = "\n".join(f"line_{index}" for index in range(1, 121))

    chunks = chunk_code("octo/demo", "app/main.py", content, max_lines=50, overlap=10)

    assert len(chunks) == 3
    assert chunks[0].path == "app/main.py"
    assert chunks[0].language == "python"
    assert chunks[1].start_line == 41


def test_language_for_path() -> None:
    assert language_for_path("src/app.ts") == "typescript"
    assert language_for_path("README.md") == "md"
