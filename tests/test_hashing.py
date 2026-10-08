import os
import pytest
from app.services.hashing import calculate_sha256

def test_calculate_sha256(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "hello.txt"
    p.write_text("hello world")
    
    # sha256 of 'hello world' is b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
    expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
    assert calculate_sha256(str(p)) == expected_hash

def test_calculate_sha256_missing_file():
    assert calculate_sha256("non_existent_file.txt") is None
