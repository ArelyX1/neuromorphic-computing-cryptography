import numpy as np
from numpy.random import default_rng
from typing import Optional, Tuple, List


class MemristorCrossbar:
    def __init__(self, rows: int, cols: int, seed: int):
        self.rng = default_rng(seed + 999)
        self.rows = rows
        self.cols = cols
        self.conductances = np.abs(self.rng.normal(loc=0.5, scale=0.15, size=(rows, cols)))
        self.conductances = np.clip(self.conductances, 0.01, 1.0)
        self.bound = 1.0

    def stdp_update(self, pre_spikes: np.ndarray, post_spike: bool, lr: float = 0.01):
        delta = np.zeros((self.rows, self.cols))
        for i in range(self.rows):
            for j in range(self.cols):
                if pre_spikes[j] and post_spike:
                    delta[i, j] = lr * (self.bound - self.conductances[i, j])
                elif pre_spikes[j] and not post_spike:
                    delta[i, j] = -lr * self.conductances[i, j]
        self.conductances = np.clip(self.conductances + delta, 0.01, self.bound)

    def read_current(self, voltages: np.ndarray) -> np.ndarray:
        return self.conductances @ voltages


class LIFNeuron:
    def __init__(self, threshold: float = 1.0, reset: float = 0.0, leak: float = 0.9):
        self.threshold = threshold
        self.reset = reset
        self.leak = leak
        self.membrane = 0.0

    def step(self, current: float) -> bool:
        self.membrane = self.leak * self.membrane + current
        if self.membrane >= self.threshold:
            self.membrane = self.reset
            return True
        return False

    def reset_state(self):
        self.membrane = 0.0


class NeuromorphicPUFPreprocessor:
    def __init__(self, key: str, n: int = 64):
        self.key = key
        self.n = n
        self.rng = default_rng(seed=abs(hash(key)) % (2**31))

    def spike_encode(self, challenge: np.ndarray) -> np.ndarray:
        rate = (challenge + 1) / 2.0
        spikes = (self.rng.random(self.n) < rate).astype(np.float32)
        return spikes

    def process(self, challenge: np.ndarray) -> np.ndarray:
        spikes = self.spike_encode(challenge)
        for i in range(len(spikes)):
            shift = ord(self.key[i % len(self.key)]) % 32
            spikes[i] *= (1.0 + 0.01 * shift)
        return spikes


class NeuromorphicHybridPUF:
    def __init__(
        self,
        n: int = 64,
        k: int = 4,
        noisiness: float = 0.02,
        seed: Optional[int] = None,
        preprocessor_key: str = "NEURODRONE2024",
        t_window: int = 10,
    ):
        if seed is None:
            seed = int.from_bytes(b"NEUROMORPHIC_PUF_DRONE", byteorder='big') % (2**31)
        self.n = n
        self.k = k
        self.noisiness = noisiness
        self.seed = seed
        self.t_window = t_window
        self.rng = default_rng(seed)

        self.crossbar = MemristorCrossbar(rows=k, cols=n, seed=seed)
        self.neurons = [LIFNeuron(threshold=1.0, leak=0.9) for _ in range(k)]
        self.bias = self.rng.normal(loc=0, scale=0.5, size=(k,))

        self.preprocessor = NeuromorphicPUFPreprocessor(preprocessor_key, n)
        self.stdp_active = False

    @property
    def challenge_length(self) -> int:
        return self.n

    @property
    def response_length(self) -> int:
        return 1

    def enable_learning(self, active: bool = True):
        self.stdp_active = active

    def eval(self, challenge: np.ndarray, noisy: bool = False) -> int:
        spikes = self.preprocessor.process(challenge)
        voltages = spikes

        crossbar_output = self.crossbar.read_current(voltages) + self.bias

        for t in range(self.t_window):
            for i in range(self.k):
                noise = 0.0
                if noisy:
                    noise = self.rng.normal(0, self.noisiness)
                current = crossbar_output[i] + noise
                spiked = self.neurons[i].step(current)

                if self.stdp_active and i == 0 and t == self.t_window - 1:
                    pre_activity = (voltages > 0.5).astype(np.float32)
                    self.crossbar.stdp_update(pre_activity, spiked, lr=0.005)

        final_spikes = []
        for i in range(self.k):
            final_spikes.append(self.neurons[i].membrane)
            self.neurons[i].reset_state()

        combined = np.prod(final_spikes)
        if noisy:
            combined += self.rng.normal(0, self.noisiness * 2)
        return 1 if combined >= 0 else -1

    def generate_challenge(self) -> np.ndarray:
        raw = self.rng.choice([-1, 1], size=self.n).astype(np.int8)
        return raw

    def generate_crp_pair(self, noisy: bool = False) -> Tuple[np.ndarray, int]:
        challenge = self.generate_challenge()
        response = self.eval(challenge, noisy=noisy)
        return challenge, response

    def generate_crp_set(self, N: int, noisy: bool = False) -> Tuple[np.ndarray, np.ndarray]:
        challenges = np.zeros((N, self.n), dtype=np.int8)
        responses = np.zeros(N, dtype=np.int8)
        for i in range(N):
            c, r = self.generate_crp_pair(noisy)
            challenges[i] = c
            responses[i] = r
        return challenges, responses

    def bits_to_bytes(self, bits: np.ndarray) -> bytes:
        bits_01 = ((bits + 1) // 2).astype(np.uint8)
        byte_list = []
        for i in range(0, len(bits_01), 8):
            chunk = bits_01[i:i+8]
            if len(chunk) < 8:
                chunk = np.pad(chunk, (0, 8 - len(chunk)), constant_values=0)
            byte_val = sum(int(b) << (7 - j) for j, b in enumerate(chunk))
            byte_list.append(byte_val)
        return bytes(byte_list)


class PUFVigenerePreprocessor:
    def __init__(self, key: str):
        self.key = key

    def process(self, challenge: np.ndarray) -> np.ndarray:
        modified = challenge.copy().astype(np.int8)
        for i in range(len(modified)):
            shift = ord(self.key[i % len(self.key)]) % 32
            modified[i] = np.int8((-1) ** (shift % 2)) * modified[i]
        return modified


class PUFCaesarPreprocessor:
    def __init__(self, shift: int = 3):
        self.shift = shift % 2

    def process(self, challenge: np.ndarray) -> np.ndarray:
        if self.shift == 0:
            return challenge
        return -challenge


class PUFXORPreprocessor:
    def __init__(self, xor_key: np.ndarray):
        self.xor_key = xor_key

    def process(self, challenge: np.ndarray) -> np.ndarray:
        return np.bitwise_xor(
            (challenge + 1) // 2,
            (self.xor_key + 1) // 2
        ).astype(np.int8) * 2 - 1


class HybridPUF(NeuromorphicHybridPUF):
    def __init__(
        self,
        n: int = 64,
        k: int = 4,
        noisiness: float = 0.02,
        seed: Optional[int] = None,
        preprocessor: str = "vigenere",
        preprocessor_key: str = "DRONEKEY2024",
        t_window: int = 10,
    ):
        super().__init__(
            n=n, k=k, noisiness=noisiness,
            seed=seed, preprocessor_key=preprocessor_key,
            t_window=t_window,
        )
        self._legacy_preprocessor_name = preprocessor
        self._legacy_preprocessor_key = preprocessor_key
        if preprocessor == "vigenere":
            self.preprocessor = PUFVigenerePreprocessor(preprocessor_key)
        elif preprocessor == "caesar":
            self.preprocessor = PUFCaesarPreprocessor(3)
        elif preprocessor == "xor":
            xor_key = self.rng.choice([-1, 1], size=n).astype(np.int8)
            self.preprocessor = PUFXORPreprocessor(xor_key)
        else:
            self.preprocessor = None
        self._legacy_mode = True

    def _ltf_val(self, challenge: np.ndarray, ltf_idx: int) -> float:
        return np.dot(self.crossbar.conductances[ltf_idx], challenge.astype(np.float32)) + self.bias[ltf_idx]

    def eval(self, challenge: np.ndarray, noisy: bool = False) -> int:
        if not self._legacy_mode:
            return super().eval(challenge, noisy)

        processed = challenge.astype(np.int8)
        if self.preprocessor:
            processed = self.preprocessor.process(processed)

        sub_results = np.array([
            self._ltf_val(processed, i) for i in range(self.k)
        ])

        if noisy:
            noise = self.rng.normal(loc=0, scale=self.noisiness, size=self.k)
            sub_results += noise

        combined = np.prod(sub_results)
        return 1 if combined >= 0 else -1
