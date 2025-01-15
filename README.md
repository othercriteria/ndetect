# `ndetect`: Near-Duplicate Detection using MinHash

## Core Behavior

### 1. Identify Near-Duplicates

- The tool identifies near-duplicate text documents based on their **content similarity** using MinHash.
- **Groups** of duplicates are formed by detecting transitive relationships (e.g., if A is similar to B and B is similar to C, all three form a group).

### 2. Modes of Operation

The tool operates in two primary modes:

1. **Interactive Mode** (default):
   - Groups of duplicates are displayed in a clear tabular format, showing:
     - File paths
     - File sizes (in bytes)
     - Modification timestamps
     - Approximate similarity percentage
   - Actions include:
     - Keeping all files in a group
     - Deleting specific duplicates
     - Moving duplicates to a designated directory
     - Viewing detailed information
     - Skipping groups
     - Quitting the program
2. **Non-Interactive Mode**:
   - Automatically processes files according to specified criteria without user interaction
   - Supports configurable options for:
     - Similarity threshold
     - Criteria to determine which file to keep (e.g., age, size)
     - Output directory for duplicates
     - Logging of actions

### **3. Text-Likeness Detection**

- The tool automatically excludes files that are not text-like
- Criteria for exclusion:
  - Low ratio of printable characters in the file content
  - Decoding errors when reading as UTF-8
  - File extension filters (defaults to .txt, .md, .log, .csv)

## User Interface

### Interactive Mode

1. **Initialization**:
   - Shows a progress spinner while scanning files
   - Reports the total number of valid text files found

2. **Group Presentation**:
   - Each group is displayed in a bordered panel showing:

     ```bash
     ~94.53% similar
     ┏━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
     ┃   ┃ File                                  ┃         Size ┃         Modified ┃
     ┡━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
     │ 1 │ ../numpy-2.2.1.dist-info/LICENSE.txt  │ 47,755 bytes │ 2025-01-13 13:57 │
     │ 2 │ ../scipy-1.15.1.dist-info/LICENSE.txt │ 46,845 bytes │ 2025-01-13 13:57 │
     └───┴───────────────────────────────────────┴──────────────┴──────────────────┘
     ```

   - For groups with 2 files: Shows "~XX.XX% similar"
   - For groups with 3+ files: Shows "~XX.XX% avg. similarity"

3. **Available Actions**:
   - **[k] Keep all**: No changes are made to this group, and it won't appear again
   - **[d] Delete duplicates**: Select files to delete
   - **[m] Move duplicates**: Select files to move (not yet implemented)
   - **[i] Show details**: Display detailed information including:
     - File metadata (size, timestamps, permissions)
     - Pairwise similarity scores
     - Content previews
   - **[q] Quit**: Exit the program

4. **Group Management**:
   - Groups are presented in order of highest similarity first
   - Each group remains active until explicitly handled (keep, delete, or move)
   - After any file operation, groups are automatically recalculated
   - Detailed information can be viewed multiple times while working with a group

## User Flow

### Interactive Mode Flow

1. **Initialization**:
   - The tool scans the provided file paths, identifies text-like files, and computes MinHash signatures.
   - Files are grouped based on content similarity.

2. **Group Presentation**:
   - Duplicate groups are presented to the user, e.g.:

     ```bash
     Found duplicate groups:
     [1] file1.txt, file2.txt
     [2] file3.txt, file4.txt, file5.txt
     ```

   - The user is prompted to act on each group.

3. **Available Actions**:
   - **[k] Keep all**: No changes are made to this group.
   - **[d] Delete duplicates**: The user selects which files to delete from the group.
   - **[m] Move duplicates to holding**: The user selects files to move to a holding directory.
   - **[i] Show details**: Show similarity scores for the group or detailed file metadata.

4. **Dynamic Updates**:
   - After each action, groups are recalculated to account for changes (e.g., removed or moved files).
   - Similarities are **not re-computed**; groups are updated based on the existing similarity graph.

### Non-Interactive Mode

1. **Batch Processing**:
   - Groups are formed automatically based on the similarity threshold.
   - Actions are applied based on user-defined criteria:
     - **Similarity threshold**: (e.g., 0.85).
     - **Retention criteria**: Keep files based on:
       - Smallest size.
       - Oldest or newest modification time.
       - Priority paths (e.g., files in `/important`).
   - Example behavior: For a group of duplicates:
     - Retain the oldest file and move the rest to the purgatory directory.
2. **Logging**:
   - Outputs a log file summarizing actions taken (e.g., files moved, deleted, or skipped).

## Key Features

### 1. MinHash-Based Similarity

- Efficiently calculates content similarity for large collections of text documents.
- Groups duplicates using a **similarity graph**:
  - Nodes represent files.
  - Edges represent pairs of files with similarity above the threshold.
- Implementation details:
  - Document fingerprinting using k-shingles:
    - Text is normalized (lowercase, whitespace normalized)
    - Content is split into overlapping k-shingles (default k=5)
    - Each shingle is hashed and added to MinHash signature
  - Similarity calculation:
    - Jaccard similarity between MinHash signatures
    - Configurable number of permutations (default: 128)
    - Configurable shingle size for different use cases

### 2. Text-Likeness Detection

- Files that fail basic text-likeness checks are excluded from processing.
- Includes:
  - Decoding as UTF-8.
  - Checking for printable character ratio.
  - Optional file extension filters.

### 3. Dynamic Group Management

- Groups are updated dynamically as actions are taken (e.g., deleting or moving files).
- Ensures that changes are immediately reflected in the presented groups.

### 4. Configurable Threshold

- Users can specify a similarity threshold (e.g., 0.85) to adjust the sensitivity of duplicate detection.

### 5. File Retention Criteria

- In non-interactive mode, users can specify criteria for which file to retain within a group:
  - **Age**: Oldest or newest.
  - **Size**: Smallest or largest.
  - **Priority paths**: Retain files in certain directories.

### 6. Logging

- Logs all actions taken, including files excluded from processing and duplicates detected.
- Log format: human-readable text or structured formats like JSON.

## Command-Line Interface

### Interactive Mode (default)

```bash
ndetect /path/to/files
```

### Non-Interactive Mode Flow

```bash
ndetect --mode non-interactive --threshold 0.9 --holding-dir /purgatory --criteria size --log /output/log.txt
```

### Additional Options

- `--threshold [float]`: Set similarity threshold (default: 0.85).
- `--criteria [size|age|priority]`: Specify retention criteria (default: none).
- `--holding-dir [path]`: Directory to move duplicates in non-interactive mode.
- `--log [path]`: Path to the log file (default: stdout).
- `--skip-non-text`: Exclude non-text files.
- `--dry-run`: Show actions without making changes.

## Minimum Viable Product (MVP) Scope

### 6. Interactive Mode

#### Completed ✅

- Basic group display interface
- Action menu structure
- File deletion implementation
- Detailed file information view
- Enhanced group display with file details
- Progress indication for graph building
- Group persistence until explicitly handled
- Safe file operation handling

#### In Progress 🚧

- Move to holding directory implementation
- Keyboard shortcuts and navigation

### 7. Non-Interactive Mode 🚧

- Automated processing logic
- Retention criteria implementation
- Batch operations
- Action logging
- Report generation
- Dry-run mode

### 8. Error Handling

#### Completed ✅

- Basic validation for file operations
- Type checking and validation
- Standard error messages

#### In Progress 🚧

- Enhanced error recovery mechanisms
- User-friendly error messages
- Operation rollback capabilities
- Detailed error logging

Legend:
✅ - Complete
🚧 - Not Started/In Progress

## Future Considerations (Post-MVP)

- Hierarchical grouping for large collections.
- Undo functionality.
- Enhanced heuristics for text-likeness detection (e.g., natural language detection).
- Configurable grouping behavior (e.g., similarity banding).

## Technical Details

### Text Processing

- Files are validated for UTF-8 encoding and minimum printable character ratio
- Text content is normalized (lowercase, whitespace normalized)
- Content is split into overlapping k-shingles (default k=5)
- MinHash signatures are generated using configurable permutations (default: 128)

### Similarity Detection

- Files are compared using MinHash-based Jaccard similarity
- Groups are formed using connected components with transitive relationships
- Groups are presented in order of highest similarity first
- Performance optimizations:
  - Cached MinHash signatures
  - Batched processing for memory efficiency
  - Dynamic group updates after operations

## Configuration

The following parameters can be customized:

- `--num-perm`: Number of MinHash permutations (default: 128)
- `--shingle-size`: Size of text shingles (default: 5)
- `--threshold`: Minimum similarity threshold (default: 0.8)
- `--min-printable`: Minimum ratio of printable characters (default: 0.8)
