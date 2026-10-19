# Prismatic Moon reference documents

Local, immutable copies of the public documentation distributed by the Prismatic Moon author. These files are retained so analysis tools and future sessions do not depend on Google Drive being reachable.

- Source folder: <https://drive.google.com/drive/folders/1W-TbF-XashTxOjQj6A4jdj4IkYFBEBVD>
- Retrieved: 2026-09-19 (America/Phoenix)
- Integrity and original Google Drive IDs: [`MANIFEST.json`](MANIFEST.json)
- Upstream ownership: these reference documents remain the property of their original author(s); this directory is a source snapshot, not project-authored game data.

The shared `Wild Pokemon Locations.pdf` is retained once at [`../Wild Pokemon Locations.pdf`](../Wild%20Pokemon%20Locations.pdf), which is the canonical copy used by the project. The former copy in this directory was byte-identical; it was removed to avoid two files representing one upstream artifact. The manifest lists the Prismatic Moon-specific files retained here.

## Data priority for this project

For the user's **Prismatic Moon Standard** playthrough:

1. Use the Standard-specific documents and shared hack documents in this directory for changed encounters, evolution methods, level-up moves, vendors, special encounters, Mega Evolution, and trainer/totem details.
2. Use pinned vanilla Generation VII data only where these documents do not override it.
3. Use the Rebalanced documents only when explicitly analysing the Rebalanced variant. They are retained for completeness but are not authoritative for the user's Standard run.
4. Use historical Smogon data only for competitive context, not acquisition legality.

`Level Up Moves, Standard.txt` and `Level Up Moves, Rebalanced.txt` are UTF-16 text files exactly as served upstream. The PDFs are exact upstream bytes; some pages in `Wild Pokemon Locations.pdf` are image-based and may require OCR for text search.

## Programmatic Standard form identity

`tools.story_moves.standard_target_levels()` returns manifest-verified Standard level-up tables keyed by collection identity, including `52:kanto` and `52:alolan`. Alternate-form headings use internal USUM table numbers, not new National Dex species: Alolan Meowth and Persian occupy records 922 and 923 in this retained source. The resolver uses the shared, hash-verified personal-table mapping and cross-checks the creator's header for every regional target; it refuses mismatched catalogue identities or altered binary sources rather than borrowing another form's moves.

```python
from tools.story_moves import standard_target_levels
levels = standard_target_levels()
alolan_meowth = levels["52:alolan"]
kanto_meowth = levels["52:kanto"]
```

The legacy `standard_levels()` API still returns raw document records, and numeric National Dex keys in the new projection retain the regular form's original meaning. A consumer wanting the Alolan default must request its explicit key. Internal record numbers are not valid collection/search species IDs. This documents the source-loader API, not proof that every app/report consumer has migrated to it; implementation progress is tracked in #17.
