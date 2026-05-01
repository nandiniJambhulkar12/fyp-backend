import os
try:
    import torch
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import numpy as np
    HAS_TRANSFORMERS = True
except Exception:
    HAS_TRANSFORMERS = False

MODEL_DIR = os.environ.get(
    'MODEL_DIR',
    os.path.join(
        os.path.dirname(__file__),
        '..',
        '..',
        'models',
        'artifacts',
    ),
)
MODEL_NAME = os.environ.get('MODEL_NAME', 'microsoft/codebert-base')


class DummyModel:
    """Fallback model used when transformers/torch are unavailable.

    It returns a safe default: label 0 (no vulnerability) with low confidence.
    """
    def predict(self, code_text: str):
        return 0, 0.0


if HAS_TRANSFORMERS:
    class VulnerabilityModel:
        def __init__(self, model_dir=None):
            self.model_dir = model_dir or MODEL_DIR
            self.device = torch.device(
                'cuda' if torch.cuda.is_available() else 'cpu'
            )
            self._load()

        def _load(self):
            if os.path.exists(self.model_dir) and os.listdir(self.model_dir):
                try:
                    self.tokenizer = (
                        AutoTokenizer.from_pretrained(self.model_dir)
                    )
                    self.model = (
                        AutoModelForSequenceClassification
                        .from_pretrained(self.model_dir)
                    )
                    self.model.to(self.device)
                    return
                except Exception:
                    pass
            # fallback to base model
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
            self.model = (
                AutoModelForSequenceClassification.from_pretrained(
                    MODEL_NAME, num_labels=2
                )
            )
            self.model.to(self.device)

        def predict(self, code_text: str):
            inputs = self.tokenizer(
                code_text,
                return_tensors='pt',
                truncation=True,
                max_length=512,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            self.model.eval()
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits.cpu().numpy()[0]
                probs = torch.softmax(torch.tensor(logits), dim=0).numpy()
                label = int(np.argmax(probs))
                confidence = float(np.max(probs))
            return label, confidence

    # singleton
    _model = None

    def get_model():
        global _model
        if _model is None:
            _model = VulnerabilityModel()
        return _model
else:
    # Provide a lightweight fallback so the API stays responsive
    # without heavy deps.
    _model = DummyModel()

    def get_model():
        return _model
