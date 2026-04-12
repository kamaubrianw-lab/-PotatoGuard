"""
app/inference.py
================
TFLite inference engine — singleton, thread-safe.

Model location : potato_disease_app/models/efficientnet_potato_quant.tflite
Input spec     : (1, 224, 224, 3)  float32  [0, 255]  — NO external normalisation.
Output spec    : (1, 3)  INT8 logits  →  dequantised  →  softmax probabilities.

BatchNorm stability note
------------------------
EfficientNetB0's TFLite graph contains an internal Rescaling op that converts
raw float32 [0-255] → the model-expected float range.  Feeding pre-normalised
floats would shift the inputs past the BatchNorm running statistics baked in
during quantisation, producing completely wrong predictions.
Always pass raw 0-255 pixels (cast to float32).
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT      = Path(__file__).resolve().parent.parent             # potato_disease_app/
MODEL_PATH = _ROOT / "models" / "efficientnet_potato_quant.tflite"

# ---------------------------------------------------------------------------
# Class registry  (order must match training export)
# ---------------------------------------------------------------------------
CLASS_NAMES: list[str] = [
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
]

DISPLAY_NAMES: dict[str, str] = {
    "Potato___Early_blight": "Early Blight (Alternaria solani)",
    "Potato___Late_blight" : "Late Blight (Phytophthora infestans)",
    "Potato___healthy"     : "Healthy",
}

INPUT_SIZE: tuple[int, int] = (224, 224)


# ---------------------------------------------------------------------------
# Singleton interpreter
# ---------------------------------------------------------------------------
class _TFLiteInterpreter:
    """
    Thread-safe singleton that holds the TFLite Interpreter in memory.
    Only one instance is ever created (double-checked locking pattern).
    """

    _instance   : Optional["_TFLiteInterpreter"] = None
    _class_lock : threading.Lock                  = threading.Lock()

    def __new__(cls) -> "_TFLiteInterpreter":
        if cls._instance is None:
            with cls._class_lock:
                if cls._instance is None:          # second check inside lock
                    obj = super().__new__(cls)
                    obj._load()
                    cls._instance = obj
        return cls._instance

    # ------------------------------------------------------------------
    def _load(self) -> None:
        """Load and allocate the interpreter exactly once."""
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"\n\nModel file not found:\n  {MODEL_PATH}\n\n"
                "Copy 'efficientnet_potato_quant.tflite' into the "
                "'models/' directory at the project root.\n"
            )

        # Prefer lightweight tflite-runtime; fall back to full TensorFlow
        try:
            import tflite_runtime.interpreter as tflite   # type: ignore
            Interpreter = tflite.Interpreter
            logger.info("Loaded via tflite-runtime.")
        except ImportError:
            try:
                import tensorflow as tf                    # type: ignore
                Interpreter = tf.lite.Interpreter
                logger.info("Loaded via tensorflow.lite (tflite-runtime not found).")
            except ImportError as exc:
                raise RuntimeError(
                    "Neither tflite-runtime nor tensorflow is installed.\n"
                    "Run:  pip install tflite-runtime"
                ) from exc

        self._interp         = Interpreter(model_path=str(MODEL_PATH))
        self._interp.allocate_tensors()
        self._input_details  = self._interp.get_input_details()
        self._output_details = self._interp.get_output_details()
        self._infer_lock     = threading.Lock()

        logger.info("TFLite model ready | input=%s | output=%s",
                    self._input_details[0]["shape"],
                    self._output_details[0]["shape"])

    # ------------------------------------------------------------------
    def run(self, array: np.ndarray) -> np.ndarray:
        """
        Execute inference on a pre-processed float32 array.

        Parameters
        ----------
        array : np.ndarray  shape (1, 224, 224, 3), dtype float32

        Returns
        -------
        np.ndarray  raw INT8 output, shape (1, 3)
        """
        with self._infer_lock:
            self._interp.set_tensor(self._input_details[0]["index"],  array)
            self._interp.invoke()
            return self._interp.get_tensor(self._output_details[0]["index"])

    @property
    def output_details(self) -> dict:
        return self._output_details[0]


# ---------------------------------------------------------------------------
# Module-level singleton handle
# ---------------------------------------------------------------------------
_interpreter: Optional[_TFLiteInterpreter] = None


def load_model() -> None:
    """
    Eagerly initialise the singleton interpreter.
    Call this once from FastAPI's startup event so the first real
    request pays zero model-loading latency.
    """
    global _interpreter
    _interpreter = _TFLiteInterpreter()
    logger.info("Inference engine ready.")


def _get_interpreter() -> _TFLiteInterpreter:
    global _interpreter
    if _interpreter is None:
        _interpreter = _TFLiteInterpreter()
    return _interpreter


# ---------------------------------------------------------------------------
# Pre-processing
# ---------------------------------------------------------------------------
def _preprocess(pil_image: Image.Image) -> np.ndarray:
    """
    Resize to 224×224, convert to RGB, cast to float32.

    IMPORTANT: Do NOT normalise.  The model's internal Rescaling layer
    expects raw [0, 255] pixels — pre-normalising breaks BatchNorm stats.
    """
    img = pil_image.convert("RGB").resize(INPUT_SIZE, Image.BILINEAR)
    arr = np.array(img, dtype=np.float32)         # (224, 224, 3)  [0, 255.0]
    return np.expand_dims(arr, axis=0)            # (1, 224, 224, 3)


def _dequantize_softmax(raw: np.ndarray, output_details: dict) -> np.ndarray:
    """Convert INT8 quantised output → float32 class probabilities."""
    if raw.dtype == np.int8:
        scale      = output_details["quantization_parameters"]["scales"][0]
        zero_point = output_details["quantization_parameters"]["zero_points"][0]
        dq = (raw.astype(np.float32) - zero_point) * scale
    else:
        dq = raw.astype(np.float32)

    shifted = dq - np.max(dq, axis=-1, keepdims=True)
    exp     = np.exp(shifted)
    return exp / np.sum(exp, axis=-1, keepdims=True)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def predict(pil_image: Image.Image) -> tuple[str, float, dict[str, float]]:
    """
    Run the full inference pipeline on a PIL Image.

    Returns
    -------
    predicted_class : str
        Raw class label, e.g. 'Potato___Early_blight'
    confidence : float
        Probability of the predicted class, range [0, 1]
    all_scores : dict[str, float]
        Probability for every class
    """
    interp     = _get_interpreter()
    arr        = _preprocess(pil_image)
    raw        = interp.run(arr)
    probs      = _dequantize_softmax(raw, interp.output_details)[0]   # shape (3,)

    idx        = int(np.argmax(probs))
    cls        = CLASS_NAMES[idx]
    confidence = float(probs[idx])
    all_scores = {c: float(probs[i]) for i, c in enumerate(CLASS_NAMES)}

    logger.info("Prediction → %s (%.2f%%)", cls, confidence * 100)
    return cls, confidence, all_scores