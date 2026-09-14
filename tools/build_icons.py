#!/usr/bin/env python3
"""Download Gen VII menu icons once and build the committed 807-frame atlas."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from http.client import HTTPSConnection
from io import BytesIO
from pathlib import Path

from PIL import Image

COUNT = 807
COLUMNS = 32
FRAME = (40, 30)
HOST = "raw.githubusercontent.com"
ICON_PATH = (
    "/PokeAPI/sprites/master/sprites/pokemon/versions/generation-vii/icons/{dex}.png"
)
LICENSE_PATH = "/PokeAPI/sprites/master/LICENCE.txt"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets" / "gen7-icons.png"
LICENSE_OUT = ROOT / "references" / "PokeAPI-sprites-LICENCE.txt"


def fetch(path: str) -> bytes:
    if not path.startswith("/PokeAPI/sprites/master/"):
        raise ValueError("Only the pinned asset repository is allowed")
    connection = HTTPSConnection(HOST, timeout=30)
    try:
        connection.request(
            "GET", path, headers={"User-Agent": "pokemon-checklist-builder/1"}
        )
        response = connection.getresponse()
        if response.status != 200:
            raise RuntimeError(
                f"Asset request failed with HTTP {response.status}: {path}"
            )
        return response.read()
    finally:
        connection.close()


def fetch_icon(dex: int) -> tuple[int, Image.Image]:
    image = Image.open(BytesIO(fetch(ICON_PATH.format(dex=dex)))).convert("RGBA")
    if image.size != FRAME:
        raise ValueError(f"#{dex} has unexpected dimensions {image.size}")
    return dex, image


def main() -> None:
    icons: dict[int, Image.Image] = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(fetch_icon, dex): dex for dex in range(1, COUNT + 1)}
        for future in as_completed(futures):
            dex, image = future.result()
            icons[dex] = image

    if set(icons) != set(range(1, COUNT + 1)):
        raise RuntimeError("Icon download is incomplete")

    rows = (COUNT + COLUMNS - 1) // COLUMNS
    atlas = Image.new("RGBA", (COLUMNS * FRAME[0], rows * FRAME[1]))
    for dex, image in icons.items():
        index = dex - 1
        atlas.paste(
            image, ((index % COLUMNS) * FRAME[0], (index // COLUMNS) * FRAME[1])
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    atlas.save(OUT, optimize=True)
    LICENSE_OUT.write_bytes(fetch(LICENSE_PATH))
    print(
        f"Wrote {OUT.relative_to(ROOT)} ({atlas.width}x{atlas.height}, {OUT.stat().st_size} bytes)"
    )
    print(f"Wrote {LICENSE_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
