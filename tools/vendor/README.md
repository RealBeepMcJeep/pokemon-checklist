# Vendored third-party code

## qrcode-generator 2.0.4

- File: `qrcode-generator-2.0.4.js`, the unmodified `dist/qrcode.js` from the npm package `qrcode-generator@2.0.4` (tarball SHA-256 `02e2e18a99a90b02dad940851f59b7c3c5fd1ab79cbdece8595cb06328878159`).
- File SHA-256: `79ec86f82856005b1c887905cfccfcfbec3821ca61c7fd5a952faa5f778f791c` (checked by `tools/build_qr_experimental.py`).
- Source: <https://github.com/kazuhikoarase/qrcode-generator>. Copyright (c) 2009 Kazuhiko Arase, MIT license (header retained in the file).
- Use: inlined into `qr-experimental.html` so the page draws each QR code in the browser from its precomputed byte payload, offline and without a CDN. Byte mode with the library's default 8-bit string conversion.
