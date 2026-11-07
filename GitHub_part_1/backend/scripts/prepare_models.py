"""Download verified public model weights before starting the local worker."""

import stanza
from huggingface_hub import snapshot_download

from app.core.config import settings
from app.nlp.provider import PROCESSORS


def main():
    config = settings()
    kwargs = {"model_dir": config.stanza_dir} if config.stanza_dir else {}
    stanza.download("uk", processors=PROCESSORS, **kwargs)
    snapshot_download(
        config.nlp_model,
        revision=config.nlp_revision or None,
        allow_patterns=["*.json", "*.model", "model.safetensors", "vocab.*", "merges.txt"],
        ignore_patterns=["onnx/*", "openvino/*"],
    )


if __name__ == "__main__":
    main()
