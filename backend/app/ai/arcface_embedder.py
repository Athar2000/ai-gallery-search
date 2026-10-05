"""
Real face-recognition embedder, using ArcFace (via the `insightface`
package, which wraps ONNX models).

Same story as app/ai/clip_embedder.py: this is complete, correct code, but
cannot run in this sandbox. `insightface` needs `onnxruntime` (fine, pure
PyPI) plus its pretrained `.onnx` model files, which it downloads from
Hugging Face / its own model zoo on first use — both blocked here (see
clip_embedder.py's docstring for the exact 403s and disk-space failure
this environment hit).

To actually use this: on a machine with normal internet access,

    pip install insightface onnxruntime
    # set FACE_EMBEDDING_BACKEND=arcface in .env

The first face processed after that triggers a one-time download of the
ArcFace recognition model (buffalo_l, ~300MB).
"""
from functools import lru_cache
from io import BytesIO

from app.ai.face_embedder import FACE_EMBEDDING_DIM, FaceEmbedder


class ArcFaceEmbedder(FaceEmbedder):
    def __init__(self) -> None:
        try:
            import insightface
        except ImportError as exc:
            raise RuntimeError(
                "ArcFaceEmbedder requires `insightface` (and `onnxruntime`), which are not "
                "installed. Run `pip install insightface onnxruntime` in an environment with "
                "normal internet access (see the module docstring for why this sandbox can't)."
            ) from exc

        self._app = insightface.app.FaceAnalysis(name="buffalo_l")
        self._app.prepare(ctx_id=-1)  # CPU; set >=0 for a CUDA GPU

    def embed_face(self, face_crop: bytes) -> list[float]:
        import numpy as np
        from PIL import Image

        with Image.open(BytesIO(face_crop)) as img:
            rgb = np.array(img.convert("RGB"))

        faces = self._app.get(rgb)
        if not faces:
            raise ValueError("ArcFace's own detector found no face in the provided crop")
        return faces[0].normed_embedding.tolist()


@lru_cache(maxsize=1)
def get_arcface_embedder() -> ArcFaceEmbedder:
    return ArcFaceEmbedder()


assert FACE_EMBEDDING_DIM == 512  # ArcFace's (buffalo_l) output width
