"""
Real CLIP embedding backend, using OpenCLIP.

THIS IS THE CODE THAT MAKES SEMANTIC PHOTO SEARCH ACTUALLY WORK. It is
complete and correct, but it cannot run inside this sandbox:

  - `pip install torch` alone failed here with "No space left on device"
    (torch's CPU wheel is several GB once extracted).
  - Even with torch installed, downloading pretrained CLIP weights needs
    huggingface.co or openaipublic.azureedge.net, both of which returned
    403 from this sandbox's egress proxy (only pypi/npm/github/apt hosts
    are allowlisted — see the network_configuration this app was built
    under).

To actually use this: run the app on a machine with normal internet access
(a GPU is a large speed multiplier but not required — CPU inference works,
just slower per photo). Then:

    pip install torch open_clip_torch
    # set EMBEDDING_BACKEND=clip in .env (see app/core/config.py)

The first photo processed after that will trigger a one-time download of
the `ViT-B-32` / `openai` checkpoint (a few hundred MB) via open_clip's
normal Hugging Face Hub integration.
"""
from functools import lru_cache
from io import BytesIO

from app.ai.embedder import EMBEDDING_DIM, ImageEmbedder
from app.core.config import settings


class OpenCLIPEmbedder(ImageEmbedder):
    def __init__(self) -> None:
        try:
            import open_clip
            import torch
        except ImportError as exc:
            raise RuntimeError(
                "OpenCLIPEmbedder requires `torch` and `open_clip_torch`, which are not "
                "installed. Run `pip install torch open_clip_torch` in an environment with "
                "normal internet access (see the module docstring for why this sandbox can't)."
            ) from exc

        self._torch = torch
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._model, _, self._preprocess = open_clip.create_model_and_transforms(
            settings.CLIP_MODEL_NAME, pretrained=settings.CLIP_PRETRAINED
        )
        self._model.to(self._device).eval()
        self._tokenizer = open_clip.get_tokenizer(settings.CLIP_MODEL_NAME)

    def embed_image(self, content: bytes) -> list[float]:
        from PIL import Image

        with Image.open(BytesIO(content)) as img:
            img = img.convert("RGB")
            tensor = self._preprocess(img).unsqueeze(0).to(self._device)

        with self._torch.no_grad():
            features = self._model.encode_image(tensor)
            features /= features.norm(dim=-1, keepdim=True)

        return features.squeeze(0).cpu().tolist()

    def embed_text(self, text: str) -> list[float]:
        tokens = self._tokenizer([text]).to(self._device)
        with self._torch.no_grad():
            features = self._model.encode_text(tokens)
            features /= features.norm(dim=-1, keepdim=True)
        return features.squeeze(0).cpu().tolist()


@lru_cache(maxsize=1)
def get_clip_embedder() -> OpenCLIPEmbedder:
    """Loading the model is expensive — do it once per process."""
    return OpenCLIPEmbedder()


assert EMBEDDING_DIM == 512  # ViT-B-32's output width; keep in sync with the pgvector migration
