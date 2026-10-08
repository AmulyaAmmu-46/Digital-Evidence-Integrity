import hashlib
import os

def calculate_sha256(file_path):
    """
    Calculates the SHA-256 hash of a file.
    Reads in chunks to handle large files efficiently.
    """
    if not os.path.exists(file_path):
        return None
        
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
            
    return sha256_hash.hexdigest()
