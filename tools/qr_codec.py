"""Gen VII ordinary Pokédex QR protocol tools; not QRPK7 injection codes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image
import qrcode
import zxingcpp
from qrcode.constants import ERROR_CORRECT_L

# PKHeX.Core MemeKey.DER_3 and D_3 (PokedexAndSaveFile); public verification
# material is official/recovered source data. Signing is limited to ordinary Dex.
_PUBLIC_DER = bytes.fromhex(
    "307c300d06092a864886f70d0101010500036b003068026100"
    "b61e192091f90a8f76a6eaaa9a3ce58c863f39ae253f037816"
    "f5975854e07a9a456601e7c94c29759fe155c064eddfa111"
    "443f81ef1a428cf6cd32f9dac9d48e94cfb3f690120e8e6b"
    "9111addaf11e7c96208c37c0143ff2bf3d7e831141a973"
    "0203010001"
)
_PRIVATE_D = int(
    "775455668fff3cba3026c2d0b26b8085895958341157aeb03b6b0495ee57803e"
    "2186eb6cb2eb62a71df18a3c9c6579077670961b3a6102dabe5a194ab58c325"
    "0aed597fc78978a326db1d7b28dcccb2a3e014edbd397ad33b8f28cd525054251",
    16,
)
_PUBLIC_N = int.from_bytes(_PUBLIC_DER[0x18:0x79], "big")
_PUBLIC_E = int.from_bytes(_PUBLIC_DER[0x7B:0x7E], "big")
_RSA_BYTES = 0x60
_BLOCK = 0x10


def decode_png(path: str | Path) -> bytes:
    """Decode exactly one QR symbol from an image without text conversion."""
    with Image.open(path) as image:
        results = zxingcpp.read_barcodes(image)
    if len(results) != 1 or results[0].format != zxingcpp.BarcodeFormat.QRCode:
        raise ValueError(f"expected exactly one QR code, found {len(results)}")
    return bytes(results[0].bytes)


def _xor(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right, strict=True))


def _subkey(block: bytes) -> bytes:
    out = bytearray(16)
    for i in range(0, 16, 2):
        out[i] = (2 * block[i] + (block[i + 1] >> 7)) & 0xFF
        out[i + 1] = (2 * block[i + 1]) & 0xFF
        if i + 2 < 16:
            out[i + 1] = (out[i + 1] + (block[i + 2] >> 7)) & 0xFF
    if block[0] & 0x80:
        out[15] ^= 0x87
    return bytes(out)


def _aes_transform(sig: bytes, payload: bytes, *, decrypt: bool) -> bytes:
    key = hashlib.sha1(_PUBLIC_DER + payload).digest()[:16]
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    operation = cipher.decryptor() if decrypt else cipher.encryptor()
    blocks = [sig[i:i + _BLOCK] for i in range(0, len(sig), _BLOCK)]
    if len(sig) != _RSA_BYTES:
        raise ValueError("signature must be 96 bytes")
    if decrypt:
        temp = bytes(_BLOCK)
        for i in range(len(blocks) - 1, -1, -1):
            temp = operation.update(_xor(temp, blocks[i]))
            blocks[i] = temp
        next_xor = _subkey(_xor(temp, blocks[-1]))
        blocks = [_xor(block, next_xor) for block in blocks]
        next_xor = bytes(_BLOCK)
        for i in range(len(blocks)):
            current = blocks[i]
            plain = operation.update(current)
            blocks[i] = _xor(plain, next_xor)
            next_xor = current
    else:
        temp = bytes(_BLOCK)
        for i in range(len(blocks)):
            current = _xor(blocks[i], temp)
            blocks[i] = operation.update(current)
            temp = blocks[i]
        next_xor = _subkey(_xor(temp, blocks[0]))
        blocks = [_xor(block, next_xor) for block in blocks]
        temp = bytes(_BLOCK)
        for i in range(len(blocks) - 1, -1, -1):
            original = blocks[i]
            encrypted = operation.update(original)
            blocks[i] = _xor(encrypted, temp)
            temp = original
    operation.finalize()
    return b"".join(blocks)


def _verify_meme_data(data: bytes) -> bytes | None:
    if len(data) < _RSA_BYTES:
        return None
    prefix, signature = data[:-_RSA_BYTES], data[-_RSA_BYTES:]
    number = pow(int.from_bytes(signature, "big"), _PUBLIC_E, _PUBLIC_N)
    rsa_plain = number.to_bytes(_RSA_BYTES, "big")
    for sign_bit in (False, True):
        transformed = bytearray(rsa_plain)
        if sign_bit:
            transformed[0] |= 0x80
        clear_sig = _aes_transform(bytes(transformed), prefix, decrypt=True)
        candidate = prefix + clear_sig
        if hashlib.sha1(candidate[:-8]).digest()[:8] == candidate[-8:]:
            return candidate
    return None


@dataclass(frozen=True)
class DecodedQR:
    raw_payload: bytes
    body: bytes
    key_index: int
    species_id: int
    form: int
    gender: int
    shiny_flag: int
    both_genders_flag: int
    family: str = "ordinary-dex"


def verify_ordinary_payload(raw_payload: bytes) -> DecodedQR:
    """Verify/decrypt one ordinary Gen VII Dex payload using its POKE key tag."""
    marker = raw_payload.rfind(b"POKE")
    if marker < 0 or marker + 10 > len(raw_payload):
        raise ValueError("invalid or truncated POKE framing")
    if marker != 0x62 or len(raw_payload) != 0x6C:
        raise ValueError("invalid ordinary Dex framing length")
    if raw_payload[0x60:0x62] != b"\x00\x00":
        raise ValueError("invalid ordinary Dex padding")
    if raw_payload[marker + 8:] != b"\x00\x00":
        raise ValueError("invalid ordinary Dex trailer")
    key_index = int.from_bytes(raw_payload[marker + 4:marker + 8], "little")
    if key_index != 3:
        raise ValueError(f"unsupported MemeCrypto key index {key_index}")
    for end in (marker, marker - 2):
        if end < _RSA_BYTES:
            continue
        clear = _verify_meme_data(raw_payload[:end])
        if clear is not None:
            body = clear[-_RSA_BYTES:]
            return DecodedQR(
                raw_payload=raw_payload,
                body=body,
                key_index=key_index,
                species_id=int.from_bytes(body[0x28:0x2A], "little"),
                form=body[0x2A],
                gender=body[0x2B],
                shiny_flag=body[0x2C],
                both_genders_flag=body[0x2D],
            )
    raise ValueError("ordinary Dex signature verification failed")


def _sign_ordinary_body(body: bytes) -> bytes:
    if len(body) != _RSA_BYTES:
        raise ValueError("ordinary Dex body must be exactly 96 bytes")
    signed = bytearray(body)
    signed[-8:] = hashlib.sha1(signed[:-8]).digest()[:8]
    encrypted = bytearray(_aes_transform(bytes(signed), b"", decrypt=False))
    encrypted[0] &= 0x7F
    signature = pow(
        int.from_bytes(encrypted, "big"), _PRIVATE_D, _PUBLIC_N
    )
    return signature.to_bytes(_RSA_BYTES, "big")


def generate_ordinary_payload(
    species_id: int,
    *,
    form: int | None = None,
    gender: int | None = None,
    shiny: bool | None = None,
    both_genders: bool | None = None,
    template: bytes | None = None,
) -> bytes:
    """Create locally signed ordinary Dex data; not event or injection codes."""
    if not 1 <= species_id <= 807:
        raise ValueError("species_id must be in the supported Gen I-VII range 1..807")
    if template is None:
        raise ValueError(
            "a verified ordinary Dex template is required to preserve unknown header bytes"
        )
    body = bytearray(verify_ordinary_payload(template).body)
    if form is not None and not 0 <= form <= 255:
        raise ValueError("form must fit in one byte")
    if gender is not None and gender not in (0, 1, 2):
        raise ValueError("gender must be 0, 1, or 2")
    body[0x28:0x2A] = species_id.to_bytes(2, "little")
    if form is not None:
        body[0x2A] = form
    if gender is not None:
        body[0x2B] = gender
    if shiny is not None:
        body[0x2C] = int(shiny)
    if both_genders is not None:
        body[0x2D] = int(both_genders)
    signed = _sign_ordinary_body(bytes(body))
    return signed + b"\x00\x00POKE" + (3).to_bytes(4, "little") + b"\x00\x00"


def write_qr_png(raw_payload: bytes, path: str | Path) -> None:
    """Write a standard black-on-white QR PNG with its full quiet zone."""
    code = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_L,
        box_size=8,
        border=4,
    )
    code.add_data(raw_payload, optimize=0)
    code.make(fit=True)
    code.make_image(fill_color="black", back_color="white").save(str(path))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="decode, authenticate and inspect a QR PNG")
    inspect.add_argument("image", type=Path)
    generate = commands.add_parser("generate", help="generate an ordinary Dex QR PNG")
    generate.add_argument("species_id", type=int)
    generate.add_argument("--out", required=True, type=Path)
    generate.add_argument("--form", type=int)
    generate.add_argument("--gender", type=int, choices=(0, 1, 2))
    generate.add_argument("--shiny", action="store_true", default=None)
    generate.add_argument("--both-genders", action="store_true", default=None)
    generate.add_argument("--template", required=True, type=Path,
                          help="verified source QR PNG template (preserves unknown bytes)")
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            raw = decode_png(args.image)
            decoded = verify_ordinary_payload(raw)
            report = {
                "input": str(args.image),
                "family": decoded.family,
                "keyIndex": decoded.key_index,
                "rawPayloadHex": raw.hex(),
                "rawPayloadSha256": hashlib.sha256(raw).hexdigest(),
                "decryptedBodyHex": decoded.body.hex(),
                "decoded": {
                    "speciesId": decoded.species_id, "formId": decoded.form,
                    "genderCode": decoded.gender, "shinyFlag": decoded.shiny_flag,
                    "shiny": decoded.shiny_flag != 0,
                    "bothGendersFlag": decoded.both_genders_flag,
                },
                "signatureVerified": True,
                "consoleAcceptance": "not console tested",
            }
        else:
            template = decode_png(args.template) if args.template else None
            raw = generate_ordinary_payload(
                args.species_id, form=args.form, gender=args.gender,
                shiny=args.shiny, both_genders=args.both_genders, template=template,
            )
            record = verify_ordinary_payload(raw)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            write_qr_png(raw, args.out)
            if decode_png(args.out) != raw:
                raise ValueError("QR transport round-trip changed raw payload bytes")
            report = {
                "output": str(args.out), "speciesId": record.species_id,
                "formId": record.form, "genderCode": record.gender,
                "shiny": record.shiny_flag != 0, "keyIndex": record.key_index,
                "verification": "local-signature-and-qr-verified",
                "consoleAcceptance": "not console tested",
            }
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
