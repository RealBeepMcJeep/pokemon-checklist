# Gen VII Pokémon-receive QR events — source-backed findings

**Finding:** The event references identify two QR codes that directly unlock a Pokémon gift: Magearna in all four games and Partner Cap Pikachu in *Ultra Sun/Ultra Moon* only. They are QR Scanner event payloads—not ordinary Pokédex registration, Island Scan encounters, or serial/password Mystery Gift codes.[4][5]

- **Magearna — US/American-region original saved.** Eligible in *Sun, Moon, Ultra Sun,* and *Ultra Moon*; documented QR variants are Japanese, Taiwanese, American, PAL, and Korean.[1][4] The official Pokémon US page says finish the main story, scan via QR Scanner, then collect from the deliveryman at Antiquities of the Ages in Hau’oli City; it explicitly says the code works “indefinitely.”[1]
- **Partner Cap Pikachu — North America/PAL original saved.** Eligible only in *Ultra Sun/Ultra Moon*; American and PAL share the code, with Japanese, Taiwanese, and Korean variants also documented.[4] Scan after reaching Akala, then speak to the delivery person at Pikachu Valley.[8] Serebii says the event QR codes never expire; per-save/repeat redemption limits remain **unknown** from sources reviewed.[3]
- **Not a gift:** ordinary Alola Pokédex QRs register a Pokémon as seen and earn points; generic “Special QR” uses (including Ga-Olé/Moncollé codes) are point/registration scans. Island Scan unlocks at 100 points and starts a timed wild encounter, not a gift; the specific movie-distribution Ga-Olé discs for these two events carried event QR gifts.[3][4][5]
- **Payload observation:** both original PNGs decode to one QR payload (106 bytes). The trailing `POKE` key index is 5 for Magearna and 9 for Partner Cap Pikachu; the pinned PKHeX enum names these `MagearnaEvent` and `CapPikachuEvent`.[7] This is structural decoding/key-family identification only—not signature verification, ordinary-code signing, or a console acceptance test.

**Source limits:** Magearna has a primary Pokémon.com announcement.[1]
No official Pokémon.com Partner Pikachu event page surfaced; its eligibility and redemption details are corroborated by Bulbapedia, Serebii, and Nintendo Insider.[3][4][8]
The archived Pikachu image page marks the PNG copyrighted/fair-use; retain attribution and check rights before wider redistribution.[6]

**Artifacts:** `manifest.json` (eligibility, regions, steps, verbatim claims, image/page links, hashes, verification limits); `assets/magearna.png` and `assets/pikachu.png` (downloaded originals); `assets/*.payload.bin` (decoded raw payloads); `evidence/source-excerpts.md`; the research citation ledger. Original event payloads were not generated or altered; no game data or checklist progress was modified.

<!-- Sources block generated from the task citation ledger. -->

## Sources

[1] https://www.pokemon.com/us/news/nows-your-chance-for-magearna
[3] https://www.serebii.net/ultrasunultramoon/qrevents.shtml
[4] https://bulbapedia.bulbagarden.net/wiki/QR_Scanner
[5] https://bulbapedia.bulbagarden.net/wiki/QR_Code
[6] https://archives.bulbagarden.net/wiki/File:Partner_Cap_Pikachu_distribution_QR_Code_NA_PAL.png
[7] https://raw.githubusercontent.com/kwsch/PKHeX/542111fc8584ff29c9d1455553b8acd0e1f8a59a/PKHeX.Core/Saves/Encryption/MemeCrypto/MemeKeyIndex.cs
[8] https://www.nintendo-insider.com/ash-pikachu-qr-code-for-pokemon-ultra-sun-and-ultra-moon
