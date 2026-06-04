import torch
import snntorch as snn
import numpy as np
from typing import Optional, Tuple


class MemristorCrossbar:
    def __init__(self, rows: int, cols: int, seed: int):
        gen = torch.Generator().manual_seed(seed + 999)
        self.rows = rows
        self.cols = cols
        self.conductances = torch.clamp(
            torch.abs(torch.randn(rows, cols, generator=gen) * 0.15 + 0.5),
            0.01, 1.0
        )
        self.bound = 1.0

    def stdp_update(self, pre_spikes: torch.Tensor, post_spike: bool, lr: float = 0.01, row_idx: Optional[int] = None):
        post_val = 1.0 if post_spike else 0.0
        if row_idx is not None:
            w = self.conductances[row_idx]
            delta = lr * (
                post_val * (self.bound - w) - (1 - post_val) * w
            )
            delta *= pre_spikes
            self.conductances[row_idx] = torch.clamp(w + delta, 0.01, self.bound)
        else:
            delta = lr * (
                post_val * (self.bound - self.conductances)
                - (1 - post_val) * self.conductances
            )
            delta *= pre_spikes.unsqueeze(0)
            self.conductances = torch.clamp(self.conductances + delta, 0.01, self.bound)

    def read_current(self, voltages: torch.Tensor) -> torch.Tensor:
        current = self.conductances @ voltages
        if voltages.dim() == 1:
            current -= self.conductances.mean(dim=1) * voltages.sum()
        else:
            current -= self.conductances.mean(dim=1, keepdim=True) * voltages.sum(dim=1, keepdim=True)
        return current


class LIFNeuron:
    def __init__(self, threshold: float = 1.0, reset: float = 0.0, leak: float = 0.9):
        self.threshold = threshold
        self.reset_val = reset
        self.leak = leak
        self._lif = snn.Leaky(
            beta=leak,
            threshold=threshold,
            reset_mechanism="zero",
        )
        self._mem = torch.zeros(1)
        self.membrane = 0.0

    def step(self, current: float) -> bool:
        cur_t = torch.tensor([[current]], dtype=torch.float32)
        spk, self._mem = self._lif(cur_t, self._mem)
        self.membrane = self._mem.item()
        return spk.item() > 0.5

    def reset_state(self):
        self.membrane = 0.0
        self._mem = torch.zeros(1)


class NeuromorphicPUFPreprocessor:
    def __init__(self, key: str, n: int = 64):
        self.key = key
        self.n = n
        self._gen = torch.Generator().manual_seed(abs(hash(key)) % (2**31))

    def spike_encode(self, challenge: torch.Tensor) -> torch.Tensor:
        spikes = challenge.float()
        for i in range(len(spikes)):
            shift = ord(self.key[i % len(self.key)]) % 32
            spikes[i] *= (1.0 + 0.01 * shift)
        return spikes

    def process(self, challenge: torch.Tensor) -> torch.Tensor:
        return self.spike_encode(challenge)


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
            seed = int.from_bytes(
                b"NEUROMORPHIC_PUF_DRONE", byteorder='big'
            ) % (2**31)
        self.n = n
        self.k = k
        self.noisiness = noisiness
        self.seed = seed
        self.t_window = t_window
        torch.manual_seed(seed)
        self._np_rng = np.random.default_rng(seed)

        self.crossbar = MemristorCrossbar(rows=k, cols=n, seed=seed)
        gen_bias = torch.Generator().manual_seed(seed + 1)
        self.bias = torch.randn(k, generator=gen_bias) * 0.15
        self.neurons = [LIFNeuron(threshold=1.0, leak=0.9) for _ in range(k)]

        self.preprocessor = NeuromorphicPUFPreprocessor(preprocessor_key, n)
        self.stdp_active = False
        self.stdp_lr = 0.005

    @property
    def challenge_length(self) -> int:
        return self.n

    @property
    def response_length(self) -> int:
        return 4

    def enable_learning(self, active: bool = True):
        self.stdp_active = active

    def eval(self, challenge: np.ndarray, noisy: bool = False) -> int:
        c_tensor = torch.from_numpy(challenge.astype(np.float32))
        spikes = self.preprocessor.process(c_tensor)
        voltages = spikes
        self.last_voltages = voltages.detach().numpy()

        crossbar_output = self.crossbar.read_current(voltages) + self.bias

        for t in range(self.t_window):
            for i in range(self.k):
                noise = 0.0
                if noisy:
                    noise = torch.randn(1).item() * self.noisiness
                current = crossbar_output[i].item() + noise
                spiked = self.neurons[i].step(current)

                if self.stdp_active and t == self.t_window - 1:
                    pre_activity = (voltages > 0.5).float()
                    self.crossbar.stdp_update(pre_activity, spiked, lr=self.stdp_lr, row_idx=i)

        self.last_membranes = [n.membrane for n in self.neurons]
        response = 0
        for i in range(self.k):
            bit = 1 if self.neurons[i].membrane >= 0 else 0
            if noisy:
                bit ^= (torch.randn(1).item() > 1.5)
            response = (response << 1) | bit
            self.neurons[i].reset_state()

        return response

    def generate_challenge(self) -> np.ndarray:
        half = self.n // 2
        raw = np.ones(self.n, dtype=np.int8)
        neg_indices = self._np_rng.choice(self.n, size=half, replace=False)
        raw[neg_indices] = -1
        return raw

    def generate_crp_pair(
        self, noisy: bool = False
    ) -> Tuple[np.ndarray, int]:
        challenge = self.generate_challenge()
        response = self.eval(challenge, noisy=noisy)
        return challenge, response

    def generate_crp_set(
        self, N: int, noisy: bool = False
    ) -> Tuple[np.ndarray, np.ndarray]:
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
                chunk = np.pad(
                    chunk, (0, 8 - len(chunk)), constant_values=0
                )
            byte_val = sum(
                int(b) << (7 - j) for j, b in enumerate(chunk)
            )
            byte_list.append(byte_val)
        return bytes(byte_list)


class PUFVigenerePreprocessor:
    def __init__(self, key: str):
        self.key = key

    def process(self, challenge: np.ndarray) -> np.ndarray:
        if isinstance(challenge, torch.Tensor):
            challenge = challenge.numpy()
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
        return (
            np.bitwise_xor(
                (challenge + 1) // 2,
                (self.xor_key + 1) // 2,
            ).astype(np.int8)
            * 2
            - 1
        )


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
            xor_key = self._np_rng.choice(
                [-1, 1], size=n
            ).astype(np.int8)
            self.preprocessor = PUFXORPreprocessor(xor_key)
        else:
            self.preprocessor = None
        self._legacy_mode = True

    def _ltf_val(
        self, challenge: np.ndarray, ltf_idx: int
    ) -> float:
        c = torch.from_numpy(challenge.astype(np.float32))
        w = self.crossbar.conductances[ltf_idx]
        centered = torch.dot(w, c) - w.mean() * c.sum()
        return centered.item() + self.bias[ltf_idx].item()

    def eval(self, challenge: np.ndarray, noisy: bool = False) -> int:
        if not self._legacy_mode:
            return super().eval(challenge, noisy)

        processed = challenge.astype(np.int8)
        if self.preprocessor:
            processed = self.preprocessor.process(processed)
        self.last_voltages = (processed.astype(np.float32) + 1) / 2

        sub_results = [
            self._ltf_val(processed, i) for i in range(self.k)
        ]

        if noisy:
            noise = self._np_rng.normal(
                loc=0, scale=self.noisiness, size=self.k
            )
            for i in range(self.k):
                sub_results[i] += noise[i]

        self.last_membranes = sub_results
        response = 0
        for i in range(self.k):
            bit = 1 if sub_results[i] >= 0 else 0
            response = (response << 1) | bit

        if self.stdp_active:
            pre_activity = (torch.from_numpy(processed.astype(np.float32)) + 1) / 2
            for i in range(self.k):
                post_spike = ((response >> (3 - i)) & 1) == 1
                self.crossbar.stdp_update(pre_activity, post_spike, lr=self.stdp_lr, row_idx=i)

        return response
