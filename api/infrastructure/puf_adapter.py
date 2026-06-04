import json
import os
import hashlib
import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from typing import Optional

from ..domain.entities import EncryptedPayload
from ..domain.ports import PUFPort


class HybridPUFAdapter(PUFPort):
    def __init__(self, drone_id: str = "NEURO-DRON-01", seed: int = 777, n: int = 64, k: int = 4):
        self.drone_id = drone_id
        self.seed = seed
        self.n = n
        self.k = k
        self._puf_instance = None

    @property
    def puf(self):
        if self._puf_instance is None:
            from puf_crypto.simulation.hybrid_puf import HybridPUF
            self._puf_instance = HybridPUF(
                n=self.n, k=self.k, seed=self.seed,
                preprocessor="vigenere", preprocessor_key=self.drone_id,
            )
        return self._puf_instance

    def generate_challenge(self) -> list:
        return self.puf.generate_challenge().tolist()

    def evaluate(self, challenge: list, noisy: bool = False) -> int:
        c = np.array(challenge, dtype=np.int8)
        return int(self.puf.eval(c, noisy=noisy))

    def _puf_bit_sequence(self, challenge: list, num_bits: int) -> bytes:
        from puf_crypto.simulation.hybrid_puf import HybridPUF
        c = np.array(challenge, dtype=np.int8)
        n = self.n
        num_evals = (num_bits + n - 1) // n
        all_bits = []
        base_seed = self.seed
        for i in range(num_evals):
            noise = self.puf.noisiness + (i / max(num_evals, 1)) * 0.05
            cloned = HybridPUF(
                n=self.n, k=self.k,
                noisiness=noise,
                seed=base_seed + i + 1,
                preprocessor="vigenere",
                preprocessor_key=f"PUFKEY_DERIV_{i}",
            )
            cloned.crossbar.conductances = self.puf.crossbar.conductances.clone()
            cloned.bias = self.puf.bias.clone()
            r = cloned.eval(c, noisy=True)
            for b in range(4):
                all_bits.append((r >> (3 - b)) & 1)
        bits = np.array(all_bits, dtype=np.uint8)
        byte_list = []
        for j in range(0, len(bits), 8):
            chunk = bits[j:j+8]
            if len(chunk) < 8:
                chunk = np.pad(chunk, (0, 8 - len(chunk)), constant_values=0)
            byte_val = sum(int(b) << (7 - bi) for bi, b in enumerate(chunk))
            byte_list.append(byte_val)
        return hashlib.sha256(bytes(byte_list)).digest()

    def _derive_key(self, challenge: list, length: int = 16, salt: str = "") -> bytes:
        raw = self._puf_bit_sequence(challenge, length * 8)
        if salt:
            raw = hashlib.sha256(raw + salt.encode()).digest()
        return raw[:length]

    def encrypt(self, plaintext: bytes, challenge: list) -> EncryptedPayload:
        c = np.array(challenge, dtype=np.int8)

        # Single PUF key derivation → derive per-cipher keys via SHA-256
        master = self._derive_key(challenge, 32, salt="NEURO-PUF-MASTER")
        key_cbc = hashlib.sha256(master + b"AES-CBC").digest()[:16]
        key_ctr = hashlib.sha256(master + b"AES-CTR").digest()[:16]
        key_chacha = hashlib.sha256(master + b"ChaCha20-Final").digest()[:32]

        iv_cbc = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        cipher_cbc = Cipher(algorithms.AES(key_cbc), modes.CBC(iv_cbc))
        enc_cbc = cipher_cbc.encryptor()
        layer1 = enc_cbc.update(padded) + enc_cbc.finalize()

        nonce_ctr = os.urandom(16)
        cipher_ctr = Cipher(algorithms.AES(key_ctr), modes.CTR(nonce_ctr))
        enc_ctr = cipher_ctr.encryptor()
        layer2 = enc_ctr.update(layer1) + enc_ctr.finalize()

        pattern = ((c + 1) // 2).astype(np.uint8)
        layer3 = bytearray()
        for i, b in enumerate(layer2):
            spike = pattern[i % len(pattern)]
            perm = ((b << 1) | (b >> 7)) & 0xFF if spike else ((b >> 1) | (b << 7)) & 0xFF
            layer3.append(perm)
        layer3 = bytes(layer3)

        chacha_iv = os.urandom(16)
        cipher_chacha = Cipher(algorithms.ChaCha20(key_chacha[:32], chacha_iv), mode=None)
        enc_chacha = cipher_chacha.encryptor()
        ciphertext = enc_chacha.update(layer3) + enc_chacha.finalize()

        return EncryptedPayload(
            ciphertext=ciphertext.hex(),
            iv=chacha_iv.hex(),
            iv_cbc=iv_cbc.hex(),
            nonce_ctr=nonce_ctr.hex(),
            chacha_iv=chacha_iv.hex(),
            challenge=challenge,
            drone_id=self.drone_id,
            size=len(ciphertext),
        )

    def decrypt(self, encrypted: EncryptedPayload) -> bytes:
        c = np.array(encrypted.challenge, dtype=np.int8)

        master = self._derive_key(encrypted.challenge, 32, salt="NEURO-PUF-MASTER")
        key_chacha = hashlib.sha256(master + b"ChaCha20-Final").digest()[:32]
        chacha_iv = bytes.fromhex(encrypted.chacha_iv)
        cipher_chacha = Cipher(algorithms.ChaCha20(key_chacha[:32], chacha_iv), mode=None)
        dec_chacha = cipher_chacha.decryptor()
        layer3 = dec_chacha.update(bytes.fromhex(encrypted.ciphertext)) + dec_chacha.finalize()

        pattern = ((c + 1) // 2).astype(np.uint8)
        layer2 = bytearray()
        for i, b in enumerate(layer3):
            spike = pattern[i % len(pattern)]
            perm = ((b >> 1) | (b << 7)) & 0xFF if spike else ((b << 1) | (b >> 7)) & 0xFF
            layer2.append(perm)
        layer2 = bytes(layer2)

        key_ctr = hashlib.sha256(master + b"AES-CTR").digest()[:16]
        nonce_ctr = bytes.fromhex(encrypted.nonce_ctr)
        cipher_ctr = Cipher(algorithms.AES(key_ctr), modes.CTR(nonce_ctr))
        dec_ctr = cipher_ctr.decryptor()
        layer1 = dec_ctr.update(layer2) + dec_ctr.finalize()

        key_cbc = hashlib.sha256(master + b"AES-CBC").digest()[:16]
        iv_cbc = bytes.fromhex(encrypted.iv_cbc)
        cipher_cbc = Cipher(algorithms.AES(key_cbc), modes.CBC(iv_cbc))
        dec_cbc = cipher_cbc.decryptor()
        padded = dec_cbc.update(layer1) + dec_cbc.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()
