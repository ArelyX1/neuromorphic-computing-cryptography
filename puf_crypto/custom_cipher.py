import os
import hashlib
import numpy as np
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from .simulation.hybrid_puf import NeuromorphicHybridPUF, HybridPUF


class PUFKeyDerivation:
    def __init__(self, puf: HybridPUF):
        self.puf = puf

    def _puf_bit_sequence(self, challenge: np.ndarray, num_bits: int) -> bytes:
        n = self.puf.n
        num_evals = (num_bits + n - 1) // n
        all_bits = []
        base_seed = self.puf.seed
        for i in range(num_evals):
            noise = self.puf.noisiness + (i / max(num_evals, 1)) * 0.05
            cloned = HybridPUF(
                n=self.puf.n, k=self.puf.k,
                noisiness=noise,
                seed=base_seed + i + 1,
                preprocessor="vigenere",
                preprocessor_key=f"PUFKEY_DERIV_{i}"
            )
            cloned.crossbar.conductances = self.puf.crossbar.conductances.copy()
            cloned.bias = self.puf.bias.copy()
            r = cloned.eval(challenge, noisy=True)
            all_bits.append(r)
        bits = np.array(all_bits, dtype=np.int8)
        bits_01 = ((bits + 1) // 2).astype(np.uint8)
        byte_list = []
        for j in range(0, len(bits_01), 8):
            chunk = bits_01[j:j+8]
            if len(chunk) < 8:
                chunk = np.pad(chunk, (0, 8 - len(chunk)), constant_values=0)
            byte_val = sum(int(b) << (7 - bi) for bi, b in enumerate(chunk))
            byte_list.append(byte_val)
        return hashlib.sha256(bytes(byte_list)).digest()

    def derive_key(self, challenge: np.ndarray, length: int = 32, salt: str = "") -> bytes:
        raw = self._puf_bit_sequence(challenge, length * 8)
        if salt:
            raw = hashlib.sha256(raw + salt.encode()).digest()
        return raw[:length]


class PUFCipher:
    def __init__(self, puf: HybridPUF):
        self.puf = puf
        self.kdf = PUFKeyDerivation(puf)

    @staticmethod
    def _caesar_encrypt(data: bytes, shift: int) -> bytes:
        return bytes((b + shift) % 256 for b in data)

    @staticmethod
    def _caesar_decrypt(data: bytes, shift: int) -> bytes:
        return bytes((b - shift) % 256 for b in data)

    @staticmethod
    def _vigenere_encrypt(data: bytes, key: str) -> bytes:
        return bytes((b + ord(key[i % len(key)])) % 256 for i, b in enumerate(data))

    @staticmethod
    def _vigenere_decrypt(data: bytes, key: str) -> bytes:
        return bytes((b - ord(key[i % len(key)])) % 256 for i, b in enumerate(data))

    def _aes_cbc_encrypt(self, data: bytes, challenge: np.ndarray) -> tuple[bytes, bytes]:
        key = self.kdf.derive_key(challenge, 32, salt="AES-CBC")
        iv = os.urandom(16)
        padder = padding.PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        return encryptor.update(padded) + encryptor.finalize(), iv

    def _aes_cbc_decrypt(self, data: bytes, iv: bytes, challenge: np.ndarray) -> bytes:
        key = self.kdf.derive_key(challenge, 32, salt="AES-CBC")
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(data) + decryptor.finalize()
        unpadder = padding.PKCS7(128).unpadder()
        return unpadder.update(padded) + unpadder.finalize()

    def _aes_ctr_encrypt(self, data: bytes, challenge: np.ndarray) -> tuple[bytes, bytes]:
        key = self.kdf.derive_key(challenge, 32, salt="AES-CTR")
        nonce = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
        encryptor = cipher.encryptor()
        return encryptor.update(data) + encryptor.finalize(), nonce

    def _aes_ctr_decrypt(self, data: bytes, nonce: bytes, challenge: np.ndarray) -> bytes:
        key = self.kdf.derive_key(challenge, 32, salt="AES-CTR")
        cipher = Cipher(algorithms.AES(key), modes.CTR(nonce))
        decryptor = cipher.decryptor()
        return decryptor.update(data) + decryptor.finalize()

    def _spike_permute(self, data: bytes, challenge: np.ndarray, inverse: bool = False) -> bytes:
        pattern = ((challenge + 1) // 2).astype(np.uint8)
        result = bytearray()
        for i, b in enumerate(data):
            spike = pattern[i % len(pattern)]
            if inverse:
                perm = ((b >> 1) | (b << 7)) & 0xFF if spike else ((b << 1) | (b >> 7)) & 0xFF
            else:
                perm = ((b << 1) | (b >> 7)) & 0xFF if spike else ((b >> 1) | (b << 7)) & 0xFF
            result.append(perm)
        return bytes(result)

    def encrypt(self, plaintext: bytes, challenge: np.ndarray) -> dict:
        layer1_ct, iv_cbc = self._aes_cbc_encrypt(plaintext, challenge)
        layer2_ct, nonce_ctr = self._aes_ctr_encrypt(layer1_ct, challenge)
        layer3_ct = self._spike_permute(layer2_ct, challenge)

        chacha_key = self.kdf.derive_key(challenge, 32, salt="ChaCha20-Final")
        chacha_iv = os.urandom(16)
        cipher = Cipher(algorithms.ChaCha20(chacha_key[:32], chacha_iv), mode=None)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(layer3_ct) + encryptor.finalize()

        return {
            "ciphertext": ciphertext,
            "iv_cbc": iv_cbc,
            "nonce_ctr": nonce_ctr,
            "chacha_iv": chacha_iv,
            "challenge": challenge.tolist(),
        }

    def decrypt(self, encrypted: dict) -> bytes:
        challenge = np.array(encrypted["challenge"], dtype=np.int8)

        chacha_key = self.kdf.derive_key(challenge, 32, salt="ChaCha20-Final")
        cipher = Cipher(algorithms.ChaCha20(chacha_key[:32], encrypted["chacha_iv"]), mode=None)
        decryptor = cipher.decryptor()
        layer3_ct = decryptor.update(encrypted["ciphertext"]) + decryptor.finalize()

        layer2_ct = self._spike_permute(layer3_ct, challenge, inverse=True)
        layer1_ct = self._aes_ctr_decrypt(layer2_ct, encrypted["nonce_ctr"], challenge)
        plaintext = self._aes_cbc_decrypt(layer1_ct, encrypted["iv_cbc"], challenge)
        return plaintext
