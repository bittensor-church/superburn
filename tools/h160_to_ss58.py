#!/usr/bin/env python3
import argparse
import hashlib

BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(data: bytes) -> str:
    num = int.from_bytes(data, "big")
    encoded = ""
    while num > 0:
        num, rem = divmod(num, 58)
        encoded = BASE58_ALPHABET[rem] + encoded
    leading = 0
    for byte in data:
        if byte == 0:
            leading += 1
        else:
            break
    return "1" * leading + encoded


def h160_to_ss58(h160: str, ss58_format: int) -> str:
    h160 = h160.lower().removeprefix("0x")
    if len(h160) != 40:
        raise SystemExit("H160 address must be 20 bytes (40 hex chars)")
    addr_bytes = bytes.fromhex(h160)
    prefixed = b"evm:" + addr_bytes
    public_key = hashlib.blake2b(prefixed, digest_size=32).digest()

    if ss58_format < 64:
        prefix = bytes([ss58_format])
    else:
        ss58_format |= 0b01000000
        prefix = bytes([ss58_format & 0xFF, (ss58_format >> 8) & 0xFF])

    payload = prefix + public_key
    checksum = hashlib.blake2b(b"SS58PRE" + payload, digest_size=64).digest()[:2]

    return b58encode(payload + checksum)


def main():
    parser = argparse.ArgumentParser(description="Convert H160 (EVM) address to SS58.")
    parser.add_argument("address", help="EVM address (0x...)")
    parser.add_argument("--ss58-format", type=int, default=42, help="SS58 format (default: 42)")
    args = parser.parse_args()

    print(h160_to_ss58(args.address, args.ss58_format))


if __name__ == "__main__":
    main()
