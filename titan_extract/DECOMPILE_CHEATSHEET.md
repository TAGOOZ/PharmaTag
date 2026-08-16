# TITAN.W1 Decompilation Cheatsheet (for agent briefs)

How to decompile/analyze the TITAN.W1 VB6 P-Code app (Phye.exe). Give this to any agent that needs to research the binary. All paths are READ-ONLY unless creating a NEW doc.

## Toolchain

| Tool | Path | Usage |
|---|---|---|
| Decoder CLI | `/tmp/opencode/pcode_strings.py` | `names` / `proc <addr>` / `search "kw1,kw2"` |
| Disassembly | `/run/media/.../titan_decompile/pcode_disasm.txt` | 696k lines, ground truth |
| String pool (UTF-16) | `/run/media/.../titan_decompile/strings_utf16.txt` | 26,972 lines |
| String pool (readable) | `/run/media/.../titan_decompile/strings_readable.txt` | 18,967 lines |
| Project index | `/run/media/.../titan_decompile/project_structure.json` | objects, procs, APIs |
| UI purposes | `/run/media/.../titan_extract/ui_strings.json` | Arabic purpose per form/object |
| Decoded index maps | `/tmp/opencode/idx2refs2.json`, `idx2str2.json` | verified string→ref mapping |

## String index mapping (CRITICAL)

- `strings_utf16.txt` is a pool; **string index = 1-based line number − 3**.
- In p-code, a literal string is emitted as opcode `LitVarStr` followed by a length-prefixed byte sequence:
  - 2-byte form: `[3a <hi> <lo>]` → `idx = ((hi & 0x3F) << 8) | lo` (if b0 < 0x80)
  - 4-byte form: `idx = b[1] | (b[2] << 8) | (b[3] << 16)`  ← correct formula (older tools mis-decoded this)
- Verify with `/tmp/opencode/refmap2.py` and `idx2refs2.json`.

## Procedure layout in pcode_disasm.txt

A proc header looks like:
```
596066:[Form] FFFHisabatTree  @0x009e9c8c  size=...  frame=...
  0x0000  LitVarStr  [3a 5c ff 82 00]
  0x000c  ImpAdCallFPR4
```
- `596066:` is the line number in pcode_disasm.txt → cite as `pcode_disasm.txt:596066`.
- `@0x...` is the VB6 address (used with `pcode_strings.py proc "0x00..."`).
- Opcodes: `LitVarStr` pushes string; `MemLdRfVar`/`LateIdSt` = record/array access; `OpenFile`/`GetRecOwn4`/`PutRecOwn4`/`Close` = fixed-record `.phy` I/O; `VCallAd` = dispatch; `ForVar` = loop; `ImpAdCallFPR4` = numeric.

## Decoding strings from a proc

```
python3 pcode_strings.py names                       # all 6192 procs
python3 pcode_strings.py search "FormMrdKashf"       # find procs by name
python3 pcode_strings.py search "g1,g2,g3"           # multi-keyword
python3 pcode_strings.py proc "0x00ae56ac"           # dump decoded strings of one proc
```

## Analyzing a feature (workflow)

1. Find the object in `project_structure.json` (type: Form/Module/MDIForm/UserControl/PropertyPage).
2. `python3 pcode_strings.py search "<name>"` → list its procs.
3. Read its decoded strings → purpose (cross-check Arabic via `ui_strings.json` `forms[].purpose`).
4. In pcode_disasm.txt around each proc, look at opcodes: does it write record files (`PutRecOwn4`)? run SQL string refs? build grids (`LateIdSt` + many columns)? dispatch keys (`VCallAd`)? Only that tells you the real data flow.
5. **Dead-code check:** a string in the pool is NOT proof of use. To prove a feature runs, find a p-code reference. Use `idx2refs2.json` to count references; 0 refs = dead (e.g. all drugeye SQL was 0-ref).
6. Cross-check existing `feature_*.md` docs to avoid duplication.

## What the real data layer is

- Fixed-length record files (`.phy`) via `OpenFile`/`GetRecOwn4`/`PutRecOwn4`/`DestructRecord`/`Close` — e.g. ModDrgW loops 1..10000 (I4 id@0x00, str15@0x04, str40@0x22, prices@0x64/0x2C0).
- SQL tables exist but many table-name strings are 0-ref dead code; verify per feature.
- Sales GUID `a2a100e1-906b-44df-99c2-6e7c6098421e` (idx 7423, 3564 refs) is the central object key.

## Output rules for agents

- Write ONE new `feature_*.md` in `titan_extract/`, matching existing style (read one header first).
- Cite evidence: `pcode_disasm.txt:<line>`, `strings_utf16.txt:<line>`, `feature_*.md:<line>`.
- Mark purposes as **confirmed / inferred / unconfirmed** — never guess.
- Keep Arabic terms alongside English. Target 150–450 lines. Do not loop on reading; write as the primary action.
