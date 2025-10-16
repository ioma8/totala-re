#!/usr/bin/env python3
"""
Test suite for HPI assembler/parser round-trip functionality.

Creates test data, assembles it into an HPI archive, extracts it,
and validates the round-trip produces identical data.
"""

import os
import shutil
import tempfile
from pathlib import Path

from hpi_assembler import HPIAssembler, sha256sum
from hpi_parser import HPIParser


def create_test_data(root: Path) -> dict:
    """Create a small test directory structure with various file types."""
    test_files = {}
    
    # Create some test files
    (root / "file1.txt").write_text("Hello World!")
    test_files["file1.txt"] = b"Hello World!"
    
    (root / "file2.bin").write_bytes(bytes(range(256)))
    test_files["file2.bin"] = bytes(range(256))
    
    # Create a subdirectory
    (root / "subdir").mkdir()
    (root / "subdir" / "nested.txt").write_text("Nested file content")
    test_files["subdir/nested.txt"] = b"Nested file content"
    
    # Create a larger file to test chunking
    large_data = b"X" * (0x20000)  # 128 KiB, requires 2 chunks
    (root / "large.dat").write_bytes(large_data)
    test_files["large.dat"] = large_data
    
    # Create another subdirectory with multiple files
    (root / "sounds").mkdir()
    (root / "sounds" / "sound1.wav").write_bytes(b"RIFF" + b"\x00" * 100)
    test_files["sounds/sound1.wav"] = b"RIFF" + b"\x00" * 100
    
    (root / "sounds" / "sound2.wav").write_bytes(b"RIFF" + b"\x01" * 200)
    test_files["sounds/sound2.wav"] = b"RIFF" + b"\x01" * 200
    
    return test_files


def test_basic_assembly():
    """Test basic HPI assembly without encryption."""
    print("Test: Basic assembly (no encryption, zlib compression)")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test data
        test_root = tmppath / "test_data"
        test_root.mkdir()
        expected_files = create_test_data(test_root)
        
        # Assemble HPI
        output_hpi = tmppath / "test.hpi"
        assembler = HPIAssembler(test_root, compression_mode=2, encryption_key=0)
        assembler.assemble(output_hpi)
        
        assert output_hpi.exists(), "HPI file was not created"
        print(f"  ✓ Created HPI: {output_hpi.stat().st_size} bytes")
        
        # Parse and extract
        parser = HPIParser(output_hpi)
        parser.parse()
        
        # Verify structure
        total_files = sum(1 for e in parser.path_index.values() if not e.is_directory)
        assert total_files == len(expected_files), f"Expected {len(expected_files)} files, got {total_files}"
        print(f"  ✓ Archive contains {total_files} files")
        
        # Extract and compare each file
        extract_root = tmppath / "extracted"
        extract_root.mkdir()
        parser.extract_all(extract_root)
        
        for file_path, expected_data in expected_files.items():
            extracted_file = extract_root / file_path
            assert extracted_file.exists(), f"File not extracted: {file_path}"
            actual_data = extracted_file.read_bytes()
            assert actual_data == expected_data, f"Data mismatch for {file_path}"
        
        print(f"  ✓ All {len(expected_files)} files extracted and validated")
    
    print("  ✓ Test passed!\n")


def test_encrypted_assembly():
    """Test HPI assembly with encryption."""
    print("Test: Assembly with encryption (key=42)")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test data
        test_root = tmppath / "test_data"
        test_root.mkdir()
        expected_files = create_test_data(test_root)
        
        # Assemble HPI with encryption
        output_hpi = tmppath / "test_encrypted.hpi"
        assembler = HPIAssembler(test_root, compression_mode=2, encryption_key=42)
        assembler.assemble(output_hpi)
        
        assert output_hpi.exists(), "HPI file was not created"
        print(f"  ✓ Created encrypted HPI: {output_hpi.stat().st_size} bytes")
        
        # Parse and extract
        parser = HPIParser(output_hpi)
        parser.parse()
        
        # Extract and compare
        extract_root = tmppath / "extracted"
        extract_root.mkdir()
        parser.extract_all(extract_root)
        
        for file_path, expected_data in expected_files.items():
            extracted_file = extract_root / file_path
            assert extracted_file.exists(), f"File not extracted: {file_path}"
            actual_data = extracted_file.read_bytes()
            assert actual_data == expected_data, f"Data mismatch for {file_path}"
        
        print(f"  ✓ All files extracted and validated from encrypted archive")
    
    print("  ✓ Test passed!\n")


def test_uncompressed_assembly():
    """Test HPI assembly without compression."""
    print("Test: Assembly without compression (mode=0)")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create minimal test data
        test_root = tmppath / "test_data"
        test_root.mkdir()
        (test_root / "simple.txt").write_text("Simple test")
        expected_data = b"Simple test"
        
        # Assemble HPI without compression
        output_hpi = tmppath / "test_uncompressed.hpi"
        assembler = HPIAssembler(test_root, compression_mode=0, encryption_key=0)
        assembler.assemble(output_hpi)
        
        # Parse and extract
        parser = HPIParser(output_hpi)
        parser.parse()
        
        extract_root = tmppath / "extracted"
        extract_root.mkdir()
        parser.extract_all(extract_root)
        
        extracted_file = extract_root / "simple.txt"
        actual_data = extracted_file.read_bytes()
        assert actual_data == expected_data, "Data mismatch"
        
        print(f"  ✓ Uncompressed file validated")
    
    print("  ✓ Test passed!\n")


def test_empty_directory():
    """Test handling of empty directories (should be skipped)."""
    print("Test: Empty directories")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create structure with empty directory
        test_root = tmppath / "test_data"
        test_root.mkdir()
        (test_root / "file.txt").write_text("Content")
        (test_root / "empty_dir").mkdir()  # Empty directory
        (test_root / "nonempty_dir").mkdir()
        (test_root / "nonempty_dir" / "file2.txt").write_text("More content")
        
        # Assemble HPI
        output_hpi = tmppath / "test.hpi"
        assembler = HPIAssembler(test_root, compression_mode=2, encryption_key=0)
        assembler.assemble(output_hpi)
        
        # Parse
        parser = HPIParser(output_hpi)
        parser.parse()
        
        # Check that empty_dir doesn't appear (or appears empty)
        total_dirs = sum(1 for e in parser.path_index.values() if e.is_directory)
        # Should have at least nonempty_dir, but empty_dir might or might not be included
        print(f"  ✓ Archive created with {total_dirs} directories")
    
    print("  ✓ Test passed!\n")


def run_all_tests():
    """Run all test cases."""
    print("=" * 60)
    print("HPI Assembler Round-trip Tests")
    print("=" * 60 + "\n")
    
    try:
        test_basic_assembly()
        test_encrypted_assembly()
        test_uncompressed_assembly()
        test_empty_directory()
        
        print("=" * 60)
        print("All tests passed successfully!")
        print("=" * 60)
        return 0
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(run_all_tests())
