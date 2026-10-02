# Gen VII ordinary Pokédex QR protocol and source corpus

This toolkit is for the signed ordinary Pokédex QR family. It does not decode or generate QRPK7/PGL party-injection records, event QR codes, Magearna, Cap Pikachu, rental-team, or competition families. Those have distinct key indices and/or record formats. The generator uses only PKHeX's recovered `PokedexAndSaveFile` signing material (MemeKey index 3); it does not fabricate event signatures.

## Commands

Run in the repository's dev environment after installing `requirements-dev.txt`:

```sh
python tools/qr_codec.py inspect path/to/code.png
python tools/qr_codec.py generate 25 --out /path/to/Pikachu.png
python tools/qr_codec.py generate 722 --template references/qr-codes/images/304912.png --out /path/to/Rowlet.png
python tools/build_qr_catalog.py --root . --catalog references/qr-codes
python tools/build_qr_catalog.py --root . --catalog references/qr-codes --verify-only
```

`inspect` emits the exact transport bytes as hex, their SHA-256, the decrypted 96-byte body, the verified key index and field values. `generate` signs one ordinary record, writes a standard black/white QR with a four-module quiet zone, then checks both its signature and binary QR round-trip before reporting success. The optional template must itself be an authenticated ordinary record; recognized fields are changed only when requested, unknown bytes are kept, and the signature hash is recomputed. Without a template the body starts zero-filled. The generated record is **locally cryptographically and transport verified, not console-tested or guaranteed accepted by a particular game**.

The catalogue command explicitly refreshes the two MediaWiki category inventories and original files; it paginates API continuation tokens, requests original `imageinfo` URLs, uses a descriptive User-Agent, 30-second timeouts, three bounded attempts and at most four concurrent media downloads. A matching existing source SHA-1 is a successful-file checkpoint. `--verify-only` is offline: it rechecks original-file hashes, decodes each PNG to raw bytes, rechecks stored payload hashes and re-verifies every row marked ordinary.

## Protocol evidence and parser scope

PKHeX source revision `542111fc8584ff29c9d1455553b8acd0e1f8a59a` was inspected at `PKHeX.Core/Saves/Encryption/MemeCrypto/MemeCrypto.cs`, `MemeKey.cs`, `MemeKeyIndex.cs`, and `PKHeX.Core/Editing/PKM/QR/QRPK7.cs`. The Python verifier follows the ordinary key-index-3 path: RSA public exponentiation, the source-defined AES-ECB block/XOR transform, the truncated SHA-1 check, then field extraction from the authenticated 0x60-byte body. The source's two-byte Pokédex edge case is accepted. The corpus's ordinary examples use a 108-byte QR byte stream: a signed 96-byte record, two `00` bytes before the `POKE` marker, little-endian key index 3, and two final `00` bytes. The full byte stream and exact framing are saved per item rather than normalized through text.

The documented body fields are little-endian species ID at `0x28`, form at `0x2A`, gender code at `0x2B`, shiny flag at `0x2C`, and both-genders registration flag at `0x2D`. Unknown bytes are retained in `bodyHex`; the final eight hash bytes are regenerated on signing. `genderCode` is intentionally recorded as a raw code, not guessed into a label. Species names are looked up by the authenticated species ID in `data/pokemon.json`; filenames never override decrypted identity. Form is the protocol's numeric form code, accompanied by the exact source title.

MemeCrypto verification is not an in-game acceptance oracle. The source category a file belongs to is not regional-Dex applicability, and neither category membership nor a valid signature proves which game scanner accepts it. The reported one-way compatibility idea (Sun/Moon rejecting Ultra-only catalogue entries while Ultra accepts regular entries) remains an **unverified hypothesis**; no console or game-executable acceptance test was performed. All generation-range IDs are not thereby guaranteed usable in every game's regional Pokédex. QRPK7 is a separate 0x1A2-byte patched injection format and is not what this decoder handles.

## Corpus import and fresh cross-category audit

`manifest.json` is the single catalogue manifest. The importer queried both current API categories rather than assuming an expected inventory size. This completed import found 186 Sun/Moon memberships, 244 Ultra Sun/Ultra Moon memberships, 186 shared source pages, 0 Sun/Moon-only pages and 58 Ultra-only pages. All 244 union files were downloaded as originals and signature-verified as ordinary key-index-3 records; there were 244 distinct raw QR payloads, 198 distinct decoded species, 244 species/form pairs, zero source-label mismatches, and no failed/unsupported imports. The data file retains failure statuses if a future refresh encounters one; it does not filter them out.

Required category comparison from this live import:

- Shared Rowlet and Butterfree source pages are listed in both categories. Their payloads are ordinary Dex/key 3, 108 bytes, with `POKE` at offset 98, `0000` pre-marker padding and `0000` suffix.
- Ultra-only Ampharos and Buneary pages (including Mega Ampharos as another Ampharos form record) verify to that same ordinary family, key and framing. Their unique raw payloads establish that they are separate codes, not a new signature/framing family.
- The current source union had no Ultra-only species 803–807, Dusk Rockruff/Lycanroc form, or non-base Necrozma form; `crossCategoryProtocolAudit.ultraOnlyUSUMAdditions` is therefore empty. This says only that no such item was present in these two archive categories, not that a game cannot scan it.

All of those comparisons concern source memberships and binary protocol. They intentionally do not claim Sun/Moon-versus-Ultra in-game scan acceptance. Keep that acceptance question separate and unresolved until tested against the relevant game builds or consoles.

## Manifest shape (`schemaVersion: 1`)

```json
{
  "schemaVersion": 1,
  "provenance": { "source": "...", "api": "...", "categories": { "sun-moon": "...", "ultra-sun-ultra-moon": "..." } },
  "records": [
    {
      "source": { "pageId": 304912, "title": "File:Rowlet VII QR.png", "originalUrl": "...", "sourceSha1": "...", "categories": ["sun-moon", "ultra-sun-ultra-moon"] },
      "image": { "file": "images/304912.png", "bytes": 552 },
      "imageSha256": "...",
      "payload": { "rawHex": "...", "rawSha256": "...", "byteLength": 108, "framing": { "markerOffset": 98, "keyIndex": 3, "preMarkerHex": "0000", "suffixHex": "0000" }, "bodyHex": "..." },
      "decoded": { "species": { "id": 722, "name": "Rowlet" }, "formId": 0, "genderCode": 0, "shinyFlag": 0, "shiny": false, "bothGendersFlag": 1, "bodyBytes": 96 },
      "audit": { "status": "verified-ordinary-dex", "family": "ordinary-dex", "keyIndex": 3, "signatureVerified": true, "sourceLabelMismatch": false, "canonicalSpeciesUnknown": false, "gameAcceptance": "not-console-tested" }
    }
  ],
  "summary": { "sourceFiles": 0, "categoryMemberships": {}, "statuses": {} },
  "crossCategoryProtocolAudit": { "sharedRowletButterfree": [], "ultraOnlyOlderSpecies": [], "ultraOnlyUSUMAdditions": [] }
}
```

The example uses illustrative summary/list values; read the generated manifest for the current inventory. Every source row includes exact MediaWiki title, page ID, original URL, source SHA-1 and category memberships. Every downloaded image has a local SHA-256. Decoded payload bytes and the full 96-byte struct are retained in hex, together with hashes and framing. `audit.status` records ordinary verification, decode failure, unsupported key family, invalid/unsupported signature, or download failure; a failure remains an explicit row.

## Sources

- Published reverse-engineering discussion: <https://gbatemp.net/threads/pokemon-sun-and-moon-hacking-qr-codes.448369/>
- PKHeX source at the inspected revision: <https://github.com/kwsch/PKHeX/tree/542111fc8584ff29c9d1455553b8acd0e1f8a59a>
- Sun/Moon source category: <https://archives.bulbagarden.net/wiki/Category:Pok%C3%A9mon_Sun_and_Moon_QR_codes>
- Ultra Sun/Ultra Moon source category: <https://archives.bulbagarden.net/wiki/Category:Pok%C3%A9mon_Ultra_Sun_and_Ultra_Moon_QR_codes>
- Example original Rowlet PNG: <https://archives.bulbagarden.net/media/upload/e/ef/Rowlet_VII_QR.png>
- Example original Butterfree PNG: <https://archives.bulbagarden.net/media/upload/1/14/Butterfree_VII_QR.png>
