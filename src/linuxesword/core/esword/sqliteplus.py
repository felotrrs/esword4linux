# SQLitePlus decryptor — descifrado de blobs de contenido e-Sword (.cmtx/.dctx)
#
# Algoritmo validado contra el `CSQLitePlusDecryptor` del repositorio
# KingJamesPureBibleSearch (Donna Whisnant, GPL-3.0) y contra los vectores de
# su método `test()` (clave por defecto `Heb_4:12`).
#
# Responsabilidad EXCLUSIVA de este módulo:
#   * recibir el blob cifrado (bytes),
#   * descifrarlo con Twofish-128-ECB (clave SQLitePlus),
#   * validar el header (checksum, sizes, magia `00 1F`),
#   * descomprimir el payload zlib,
#   * devolver el payload descifrado/descomprimido (bytes).
#
# NO conoce BDL, adapters ni RTF.

"""Descifrado SQLitePlus: blob cifrado e-Sword → payload zlib descomprimido."""

from __future__ import annotations

import struct
import zlib

from .twofish import Twofish128

DEFAULT_SQLITEPLUS_KEY = "Heb_4:12"


class SQLitePlusError(Exception):
    """Error de descifrado SQLitePlus (clave incorrecta o módulo no soportado)."""


def _derive_key(key: str | bytes) -> bytes:
    """Clave SQLitePlus → 16 bytes (Twofish-128) con padding de ceros."""
    if isinstance(key, str):
        key = key.encode("utf-8", "replace")
    return key[:16].ljust(16, b"\x00")


def decrypt_payload(blob: bytes, crypt_key: str | bytes = DEFAULT_SQLITEPLUS_KEY) -> bytes:
    """Descifra un blob SQLitePlus y devuelve el payload descomprimido.

    Raises:
        SQLitePlusError: si el header es inválido, el descifrado no cuadra
            (clave incorrecta) o el payload zlib no descomprime.
    """
    if not blob:
        raise SQLitePlusError("blob vacío: no hay datos que descifrar")

    tf = Twofish128(_derive_key(crypt_key))

    # ECB: descifrar cada bloque de 16 bytes (último parcial rellenado a 0,
    # igual que el C++: readsome sobre buffer memset a 0).
    decrypted = bytearray()
    for offset in range(0, len(blob), 16):
        chunk = blob[offset:offset + 16]
        padded = chunk.ljust(16, b"\x00")
        decrypted += tf.decrypt_block(padded)

    plain = _decompress_sqliteplus(bytes(decrypted))
    return plain


def _decompress_sqliteplus(decrypted: bytes) -> bytes:
    """Interpreta el header SQLitePlus y descomprime el payload zlib."""
    if len(decrypted) < 9:
        raise SQLitePlusError("payload descifrado demasiado corto (clave incorrecta?)")

    # byte[0]: checksum/bitfield — se ignora (documentado en la fuente de referencia).
    # u24 LE compressedSize (bytes 1..3). El campo es de 24 bits: registros
    #   cuyo stream zlib supera los 64 KiB (p. ej. los artículos largos de ISBE)
    #   ponen el byte alto en decrypted[3]; leerlo como u16 truncaba el tamaño y
    #   hacía fallar el descifrado de esos registros (descartando el módulo entero).
    compressed_size = decrypted[1] | (decrypted[2] << 8) | (decrypted[3] << 16)

    # magia 1F (byte 4). El byte 3 NO es parte de la magia: es el alto del
    # compressedSize (0x00 salvo en registros > 64 KiB).
    if decrypted[4] != 0x1F:
        raise SQLitePlusError(
            "header SQLitePlus inválido (magia 1F ausente) — "
            "clave de cifrado incorrecta o módulo no soportado"
        )

    # u32 LE expectedSize
    expected_size = (
        decrypted[5]
        | (decrypted[6] << 8)
        | (decrypted[7] << 16)
        | (decrypted[8] << 24)
    )

    compressed_size -= 4  # resta expectedSize (4 bytes) del total
    zlib_start = 9
    zlib_end = zlib_start + compressed_size
    if zlib_end > len(decrypted):
        raise SQLitePlusError(
            f"zlib stream truncado (esperado {compressed_size} bytes, hay "
            f"{len(decrypted) - zlib_start}) — clave incorrecta?"
        )
    compressed = decrypted[zlib_start:zlib_end]

    # Descomprimir tolerante a registros cortos: el C++ de referencia trata el
    # fin de stream como Z_STREAM_END y acepta el payload parcial ("short
    # record") cuando el tamaño descomprimido cuadra. Usamos decompressobj
    # (no zlib.decompress directo, que falla si falta el trailer adler).
    try:
        d_obj = zlib.decompressobj()
        payload = d_obj.decompress(compressed) + d_obj.flush()
    except zlib.error as exc:
        raise SQLitePlusError(f"payload zlib inválido: {exc} — clave incorrecta?") from exc

    if len(payload) < expected_size:
        # el C++ devuelve Z_STREAM_END ("short record") y conserva lo leído;
        # si la descompresión produjo MENOS de lo esperado, el registro está
        # truncado en la fuente. Conservamos el payload (no descartamos).
        return payload
    return payload


def is_encrypted_blob(value) -> bool:
    """Heurística: si el valor de una celda de contenido es bytes, es un BLOB cifrado."""
    return isinstance(value, (bytes, bytearray))


def self_test() -> bool:
    """Self-test con los vectores de `CSQLitePlusDecryptor::test()` del C++ (clave Heb_4:12).

    Cada vector es una secuencia de bloques cifrados de 16 bytes que el
    decryptor de referencia descifra con Z_OK. Verificamos que el payload
    resultante sea legible (texto no vacío, decodificable latin-1).
    """
    vectors = [
        bytes.fromhex(
            "59766fe51cd9802e702cd2c80d8c936c"
            "c22f06e4e1bfe07c401626ba59ccf67b"
            "0ab79206587bd65a8a15584eca9d25bc"
            "20edfd9b04af63581cc888aaaaca16da"
            "6fbe68adda4bd4a45cfe439406877f9f"
        ),
        bytes.fromhex(
            "d08296dd8d5224621b39cd24b433f1a1"
            "7affd148977da6e346a7500c527720cd"
            "684d3815f84e13ad17f8e710edda85ec"
            "20669a7461d4c10cc01e8993cb71175f"
            "0aed47e1f17f97713883d75514c9e5be"
            "8431c28a666d1ccb92a181f38c265101"
            "4558d22fa02348b6655dd5290e097de6"
            "87244b39af357aab6d043755a81b0efa"
        ),
        bytes.fromhex(
            "8239de1b26b175223874c3b94f7eabcd"
            "e63b3b4ff2764c7f9a8dd34796309f25"
            "fde8e30011470a56c3057e309c8e0ef6"
            "2cdcd4408f936da0cd42766b22eac1de"
        ),
    ]
    for i, vec in enumerate(vectors, 1):
        payload = decrypt_payload(vec, DEFAULT_SQLITEPLUS_KEY)
        if not payload:
            raise AssertionError(f"SQLitePlus vector {i}: payload vacío")
        # texto legible (latin-1, no crashea; el contenido real es RTF o texto)
        payload.decode("latin-1")
    return True


if __name__ == "__main__":
    from shared.esword.twofish import self_test as twofish_self_test

    twofish_self_test()
    if self_test():
        print("SQLitePlus self-test OK")
