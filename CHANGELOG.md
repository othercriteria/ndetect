# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2024-03-21

### Added

- Comprehensive error handling system with structured logging
- Rollback functionality for failed file operations
- Disk space verification before file operations
- Detailed error messages with rich formatting
- Error recovery mechanisms for move operations
- Structured logging for all file operations
- Batch processing with atomic operations

### Changed

- Enhanced move operations to be more robust and transactional
- Improved error reporting with user-friendly messages
- Refactored file operations to handle edge cases

### Fixed

- Proper cleanup of resources in error scenarios
- Handling of permission errors during file operations
- Disk space verification before batch operations
- Memory management during large file operations

## [0.2.0] - 2024-03-21

### Added

- Initial project setup
- Basic duplicate detection functionality
- Interactive CLI interface
- Non-interactive mode
- MinHash-based similarity detection

### Changed

### Deprecated

### Removed

### Fixed

### Security
