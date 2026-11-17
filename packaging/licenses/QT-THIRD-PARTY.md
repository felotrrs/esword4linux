# Qt 6.12.0 third-party attribution

This file summarizes the attribution data shipped by Qt 6.12.0 in
`src/3rdparty/**/qt_attribution.json` for qtbase. The bundled Qt libraries
are the official Qt for Python 6.12.0 Linux wheels, which include QtBase
and QtSvg. Components that are not enabled on the Linux x86_64 build are
retained here for completeness; see the Qt source for the exact build
configuration.

Upstream: https://code.qt.io/cgit/qt/qtbase.git/tree/src/3rdparty?h=v6.12.0

| Component | SPDX license expression | Upstream license summary | Files |
|---|---|---|---|
| D3D12 Memory Allocator | MIT | MIT License |  |
| Vulkan Memory Allocator | MIT | MIT License |  |
| Native Style for Android | Apache-2.0 | Apache License 2.0 |  |
| BLAKE2 (reference implementation) | CC0-1.0 OR Apache-2.0 | Creative Commons Zero v1.0 Universal or Apache License 2.0 | src/blake2b-ref.c src/blake2s-ref.c src/blake2.h src/blake2-impl.h |
| Efficient Binary-Decimal and Decimal-Binary Conversion Routines for IEEE Doubles | BSD-3-Clause | BSD 3-clause "New" or "Revised" License |  |
| Easing Equations by Robert Penner | BSD-3-Clause | BSD 3-clause "New" or "Revised" License | easing.cpp |
| Emoji Segmenter | Apache-2.0 | Apache License 2.0 |  |
| forkfd | MIT | MIT License | forkfd.c forkfd.h forkfd_gcc.h |
| Freetype 2 | FTL OR GPL-2.0-only | Freetype Project License or GNU General Public License v2.0 only |  |
| Freetype 2 - zlib | Zlib | zlib License |  |
| Freetype 2 - Bitmap Distribution Format (BDF) support | MIT | MIT License |  |
| Freetype 2 - Portable Compiled Format (PCF) support | MIT AND MIT-open-group | MIT License and MIT Open Group variant |  |
| Gradle wrapper | Apache-2.0 | Apache License 2.0 |  |
| HarfBuzz-NG | MIT | MIT License |  |
| sRGB color profile icc file | LicenseRef-ICC-License | International Color Consortium License | sRGB2014.icc |
| LibJPEG-turbo | IJG AND BSD-3-Clause | Independent JPEG Group License and BSD 3-Clause "New" or "Revised" License |  |
| LibPNG | Libpng AND libpng-2.0 | libpng License and PNG Reference Library version 2 |  |
| The Public Suffix List | MPL-2.0 | Mozilla Public License 2.0 | psl_data.cpp |
| libpsl - C library to handle the Public Suffix List | BSD-3-Clause | BSD 3-clause "New" or "Revised" License | src/lookup_string_in_fixed_set.c src/psl-make-dafsa |
| MD4 | CC0-1.0 | Public Domain |  |
| MD4C | MIT | MIT License |  |
| MD5 | CC0-1.0 | Public Domain |  |
| PCRE2 | LicenseRef-BSD-3-Clause-with-PCRE2-Binary-Like-Packages-Exception | BSD 3-clause "New" or "Revised" License with PCRE2 binary-like Packages Exception |  |
| PCRE2 - Stack-less Just-In-Time Compiler | BSD-2-Clause | BSD 2-clause "Simplified" License |  |
| Pixman | MIT | MIT License |  |
| Secure Hash Algorithms SHA-384 and SHA-512 | BSD-3-Clause | BSD 3-clause "New" or "Revised" License |  |
| Secure Hash Algorithm SHA-1 | LicenseRef-SHA1-Public-Domain | Public Domain |  |
| Secure Hash Algorithm SHA-3 - brg_endian | BSD-2-Clause | BSD 2-clause "Simplified" License | brg_endian.h |
| Secure Hash Algorithm SHA-3 - Keccak | CC0-1.0 | Creative Commons Zero v1.0 Universal | KeccakF-1600-32-rvk.macros KeccakF-1600-32.macros KeccakF-1600-64.macros KeccakF-1600-interface.h KeccakF-1600-opt32.c KeccakF-1600-opt64.c KeccakF-1600-unrolling.macros KeccakNISTInterface.c KeccakNISTInterface.h KeccakSponge.c KeccakSponge.h |
| SipHash Algorithm | CC0-1.0 | Creative Commons Zero v1.0 Universal | siphash.cpp |
| SQLite | blessing | SQLite Blessing |  |
| TinyCBOR | MIT | MIT License |  |
| DejaVu Fonts | Bitstream-Vera | Bitstream Vera Font License | DejaVuSans.ttf DejaVuSansMono.ttf |
| Wayland KDE DBus Menu Protocol | LGPL-2.1-or-later | GNU Lesser General Public License 2.1 or later | appmenu.xml |
| Wayland Color Management Protocol | MIT | MIT License | color-management-v1.xml |
| Wayland Fractional Scale Protocol | MIT | MIT License | fractional-scale-v1.xml |
| Wayland Fullscreen Shell Protocol | MIT | MIT License | fullscreen-shell-unstable-v1.xml |
| Wayland Linux Dmabuf V1 Protocol | MIT | MIT License | linux-dmabuf-v1.xml |
| Wayland Linux Dmabuf Unstable V1 Protocol | MIT | MIT License | linux-dmabuf-unstable-v1.xml |
| Wayland Pointer Gestures Protocol | MIT | MIT License | pointer-gestures-unstable-v1.xml |
| Wayland Pointer Warp Protocol | MIT | MIT License | pointer-warp-v1.xml |
| Presentation Time Protocol | MIT | MIT License | presentation-time.xml |
| Wayland Scaler Protocol | MIT | MIT License | scaler.xml |
| Wayland Session Management Protocol | MIT | MIT License | xdg-session-management-v1.xml |
| Wayland Tablet Protocol | MIT | MIT License | tablet-unstable-v2.xml |
| Wayland Text Input Protocol v1 | MIT | MIT License | text-input-unstable-v1.xml |
| Wayland Text Input Protocol v2 | HPND | HPND License | text-input-unstable-v2.xml |
| Wayland Text Input Protocol | MIT | MIT License | text-input-unstable-v3.xml |
| Wayland Viewporter Protocol | MIT | MIT License | viewporter.xml |
| Wayland Protocol | MIT | MIT License | wayland.xml |
| Wayland EGLStream Controller Protocol | MIT | MIT License | wl-eglstream-controller.xml |
| Wlr Data Control Unstable V1 Protocol | MIT | MIT License | wlr-data-control-unstable-v1.xml |
| Wayland Primary Selection Protocol | MIT | MIT License | wp-primary-selection-unstable-v1.xml |
| Wayland xdg-activation Protocol | MIT | MIT License | xdg-activation-v1.xml |
| Wayland xdg-decoration Protocol | MIT | MIT License | xdg-decoration-unstable-v1.xml |
| Wayland Dialog Protocol | MIT | MIT License | xdg-dialog-v1.xml |
| Wayland XDG Foreign Protocol | MIT | MIT License | xdg-foreign-unstable-v2.xml |
| Wayland XDG Output Protocol | MIT | MIT License | xdg-output-unstable-v1.xml |
| Wayland XDG Shell Protocol | MIT | MIT License | xdg-shell.xml |
| Wayland XDG System Bell Protocol | MIT | MIT License | xdg-system-bell-v1.xml |
| Wayland xdg-toplevel-icon Protocol | MIT | MIT License | xdg-toplevel-icon-v1.xml |
| Wintab API | LicenseRef-Lcs-Telegraphics | LCS-Telegraphics License | pktdef.h wintab.h |
| XCB-XInput | MIT | MIT License |  |
| Data Compression Library (zlib) | Zlib | zlib License |  |
| TIFF Software Distribution (libtiff) | libtiff | libtiff License | bundled in libqtiff |
| WebP (libwebp) | BSD-3-Clause | BSD 3-clause "New" or "Revised" License | bundled in libqwebp |

## License texts

The full license texts are in `packaging/licenses/Qt/` and are installed
under `/usr/share/doc/esword4linux/licenses/Qt/`.
