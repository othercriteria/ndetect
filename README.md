### **Specification for a CLI Tool: Near-Duplicate Detection using MinHash**

---

### **Tool Name**: `ndetect`

---

### **Core Behavior**

#### **1. Identify Near-Duplicates**
- The tool identifies near-duplicate text documents based on their **content similarity** using MinHash.
- **Groups** of duplicates are formed by detecting transitive relationships (e.g., if A is similar to B and B is similar to C, all three form a group).

#### **2. Modes of Operation**
The tool operates in two primary modes:
1. **Interactive Mode** (default):
   - Groups of duplicates are displayed, allowing users to inspect and take actions manually.
   - Actions include:
     - Keeping all files in a group.
     - Deleting specific duplicates.
     - Moving duplicates to a designated "holding" directory.
     - Viewing details of similarity scores for a group.
   - Groups are recalculated dynamically after each action.
2. **Non-Interactive Mode**:
   - Automatically processes files according to specified criteria without user interaction.
   - Supports configurable options for:
     - Similarity threshold.
     - Criteria to determine which file to keep (e.g., age, size).
     - Purgatory location for duplicates.
     - Logging of actions.

#### **3. Text-Likeness Detection**
- The tool automatically excludes files that are not text-like.
- Criteria for exclusion:
  - Low ratio of printable characters in the file content.
  - Decoding errors when reading as UTF-8 or other standard encodings.
  - Optionally, file extension filters (e.g., `.txt`, `.log`, `.csv`).

---

### **User Flow**

#### **Interactive Mode**
1. **Initialization**:
   - The tool scans the provided file paths, identifies text-like files, and computes MinHash signatures.
   - Files are grouped based on content similarity.

2. **Group Presentation**:
   - Duplicate groups are presented to the user, e.g.:
     ```
     Found duplicate groups:
     [1] file1.txt, file2.txt
     [2] file3.txt, file4.txt, file5.txt
     ```
   - The user is prompted to act on each group.

3. **Available Actions**:
   - **[a] Keep all**: No changes are made to this group.
   - **[b] Delete duplicates**: The user selects which files to delete from the group.
   - **[c] Move duplicates to holding**: The user selects files to move to a holding directory.
   - **[d] Inspect details**: Show similarity scores for the group or detailed file metadata.

4. **Dynamic Updates**:
   - After each action, groups are recalculated to account for changes (e.g., removed or moved files).
   - Similarities are **not re-computed**; groups are updated based on the existing similarity graph.

#### **Non-Interactive Mode**
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

---

### **Key Features**

#### **1. MinHash-Based Similarity**
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

#### **2. Text-Likeness Detection**
- Files that fail basic text-likeness checks are excluded from processing.
- Includes:
  - Decoding as UTF-8.
  - Checking for printable character ratio.
  - Optional file extension filters.

#### **3. Dynamic Group Management**
- Groups are updated dynamically as actions are taken (e.g., deleting or moving files).
- Ensures that changes are immediately reflected in the presented groups.

#### **4. Configurable Threshold**
- Users can specify a similarity threshold (e.g., 0.85) to adjust the sensitivity of duplicate detection.

#### **5. File Retention Criteria**
- In non-interactive mode, users can specify criteria for which file to retain within a group:
  - **Age**: Oldest or newest.
  - **Size**: Smallest or largest.
  - **Priority paths**: Retain files in certain directories.

#### **6. Logging**
- Logs all actions taken, including files excluded from processing and duplicates detected.
- Log format: human-readable text or structured formats like JSON.

---

### **Command-Line Interface**

#### **Interactive Mode** (default):
```bash
ndetect /path/to/files
```

#### **Non-Interactive Mode**:
```bash
ndetect --mode non-interactive --threshold 0.9 --holding-dir /purgatory --criteria size --log /output/log.txt
```

#### **Additional Options**:
- `--threshold [float]`: Set similarity threshold (default: 0.85).
- `--criteria [size|age|priority]`: Specify retention criteria (default: none).
- `--holding-dir [path]`: Directory to move duplicates in non-interactive mode.
- `--log [path]`: Path to the log file (default: stdout).
- `--skip-non-text`: Exclude non-text files.
- `--dry-run`: Show actions without making changes.

---

### **Minimum Viable Product (MVP) Scope**

#### 1. Project Setup ✅
- Basic project structure with `pyproject.toml` and dependencies
- Development environment with Nix
- CI pipeline with linting, type checking, and tests
- Logging infrastructure

#### 2. Text-Likeness Detection ✅
- UTF-8 decoding validation
- Printable character ratio checking
- Configurable file extension filtering
- Unit tests for text detection

#### 3. CLI Framework ✅
- Argument parsing for paths and options
- Mode selection (interactive/non-interactive)
- Configurable thresholds
- Basic logging output

#### 4. MinHash Implementation ✅
- Document fingerprinting using k-shingles:
  - Text is normalized (lowercase, whitespace normalized)
  - Content is split into overlapping k-shingles (default k=5)
  - Each shingle is hashed and added to MinHash signature
- Similarity calculation:
  - Jaccard similarity between MinHash signatures
  - Configurable number of permutations (default: 128)
  - Configurable shingle size for different use cases

#### 5. Duplicate Detection 🚧
- Build similarity graph
- Group formation using transitive relationships
- Dynamic group updates
- Similarity threshold configuration

#### 6. Interactive Mode 🚧
- Group display interface
- Action menu implementation
- File operation handling (delete/move)
- Progress indication

#### 7. Non-Interactive Mode 🚧
- Automated processing logic
- Retention criteria implementation
- Batch operations
- Action logging

#### 8. Error Handling 🚧
- Graceful failure handling
- User-friendly error messages
- Recovery mechanisms
- Operation validation

Legend:
✅ - Complete
🚧 - Not Started/In Progress

---

### **Future Considerations (Post-MVP)**
- Hierarchical grouping for large collections.
- Undo functionality.
- Enhanced heuristics for text-likeness detection (e.g., natural language detection).
- Configurable grouping behavior (e.g., similarity banding).
