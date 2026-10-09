# -*- coding: utf-8 -*-
"""
DataGhost – ML document classifier.
Uses a TF-IDF + LinearSVC pipeline trained on synthetic data.

LinearSVC does NOT support predict_proba().  Confidence is derived from
the decision_function() margins and exposed as ``margin_score`` – NOT as
a probability.  Callers must not treat it as a probability value.
"""
import os
import logging
from typing import Dict, Optional

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.calibration import CalibratedClassifierCV

logger = logging.getLogger(__name__)


class DataGhostClassifier:
    """
    Classifies document text into one of four sensitivity levels:
    PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED.

    Estimator: TfidfVectorizer + LinearSVC
    LinearSVC is wrapped in CalibratedClassifierCV(cv="prefit") after
    fitting so that predict_proba() is available for downstream code
    that expects it – but consumers should note this is a calibrated
    approximation, not a true Bayesian probability.

    The raw decision_function margins are also exposed via
    ``predict_with_margins()`` and labelled ``margin_score``.
    """

    LABELS = ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]
    _PIPELINE_FILENAME = "classifier_pipeline.joblib"

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.pipeline: Optional[Pipeline] = None        # TF-IDF + LinearSVC pipeline
        self.calibrated_pipeline = None                 # CalibratedClassifierCV wrapper

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load a pre-trained pipeline from disk.  Returns True on success."""
        path = os.path.join(self.model_dir, self._PIPELINE_FILENAME)
        if not os.path.exists(path):
            logger.info("Classifier model not found at %s", path)
            return False
        try:
            saved = joblib.load(path)
            # Support both the old (plain Pipeline) and new (dict) formats.
            if isinstance(saved, dict):
                self.pipeline = saved["pipeline"]
                self.calibrated_pipeline = saved.get("calibrated")
            else:
                # Legacy: plain Pipeline saved by old LogisticRegression code.
                self.pipeline = saved
                self.calibrated_pipeline = None
            estimator_name = type(
                self.pipeline.named_steps.get("clf")
            ).__name__
            logger.info(
                "Classifier loaded from %s (estimator: %s)",
                path, estimator_name,
            )
            return True
        except Exception as exc:
            logger.warning("Failed to load classifier: %s", exc)
            return False

    def save(self):
        """Persist the current pipeline to disk."""
        os.makedirs(self.model_dir, exist_ok=True)
        path = os.path.join(self.model_dir, self._PIPELINE_FILENAME)
        joblib.dump(
            {
                "pipeline": self.pipeline,
                "calibrated": self.calibrated_pipeline,
            },
            path,
        )
        logger.info("Classifier saved to %s", path)

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, texts: list, labels: list):
        """
        Fit a TF-IDF + LinearSVC pipeline on the given texts/labels.

        After fitting the LinearSVC, a CalibratedClassifierCV wrapper is
        built so that approximate probabilities are available for callers
        that need them.  The wrapper uses sigmoid calibration.
        """
        from sklearn.model_selection import train_test_split

        # Build and fit the core TF-IDF + LinearSVC pipeline.
        self.pipeline = Pipeline(
            [
                (
                    "tfidf",
                    TfidfVectorizer(
                        ngram_range=(1, 2),
                        max_features=5000,
                        sublinear_tf=True,
                        strip_accents="unicode",
                        analyzer="word",
                        token_pattern=r"\b[a-zA-Z0-9_\.@\-]{2,}\b",
                    ),
                ),
                (
                    "clf",
                    LinearSVC(
                        C=1.0,
                        max_iter=2000,
                        random_state=42,
                        dual="auto",
                    ),
                ),
            ]
        )
        self.pipeline.fit(texts, labels)

        # Build calibrated wrapper for approximate probability output.
        # Use cv=5 cross-validated calibration — works on all sklearn versions.
        try:
            from sklearn.preprocessing import LabelEncoder
            # CalibratedClassifierCV with cv=5 refits the base estimator
            # internally and builds sigmoid-calibrated probability estimates.
            # We use a fresh LinearSVC (not the already-fitted one) so that
            # calibration folds are independent of the main training fit.
            base_svc = Pipeline(
                [
                    (
                        "tfidf",
                        TfidfVectorizer(
                            ngram_range=(1, 2),
                            max_features=5000,
                            sublinear_tf=True,
                            strip_accents="unicode",
                            analyzer="word",
                            token_pattern=r"\b[a-zA-Z0-9_\.@\-]{2,}\b",
                        ),
                    ),
                    (
                        "clf",
                        LinearSVC(
                            C=1.0,
                            max_iter=2000,
                            random_state=42,
                            dual="auto",
                        ),
                    ),
                ]
            )
            self.calibrated_pipeline = CalibratedClassifierCV(
                base_svc, cv=5, method="sigmoid"
            )
            self.calibrated_pipeline.fit(texts, labels)
            logger.info("Calibrated wrapper fitted successfully (cv=5).")
        except Exception as exc:
            logger.warning(
                "Calibration failed (%s); falling back to margin scores only.", exc
            )
            self.calibrated_pipeline = None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, text: str) -> Dict:
        """
        Classify *text* and return:

        {
          "label":        "CONFIDENTIAL",     # predicted class
          "confidence":   0.87,               # calibrated probability (approx)
                                              # OR normalised margin if no calibration
          "probabilities": {                  # per-class calibrated probs (approx)
            "PUBLIC": 0.02,
            "INTERNAL": 0.07,
            "CONFIDENTIAL": 0.87,
            "RESTRICTED": 0.04
          },
          "margin_score": 1.23,               # raw LinearSVC decision margin (NOT a probability)
          "estimator": "LinearSVC"
        }

        NOTE: ``confidence`` and ``probabilities`` are approximations from
        sigmoid calibration, NOT true Bayesian probabilities.
        ``margin_score`` is the raw LinearSVC decision_function value and
        must never be presented as a probability.
        """
        if self.pipeline is None:
            logger.warning("Classifier not trained; defaulting to PUBLIC")
            return self._default_result()

        # --- Raw LinearSVC prediction + decision margins ------------------
        predicted_label = self.pipeline.predict([text])[0]
        clf_step = self.pipeline.named_steps["clf"]
        classes = list(clf_step.classes_)

        try:
            decision = self.pipeline.decision_function([text])[0]
            if len(classes) == 2:
                # Binary case: decision_function returns a scalar.
                margin_score = float(decision)
                margin_dict = {
                    classes[0]: float(-decision),
                    classes[1]: float(decision),
                }
            else:
                # Multi-class: one margin per class.
                margin_score = float(np.max(decision))
                margin_dict = {cls: float(m) for cls, m in zip(classes, decision)}
        except Exception:
            margin_score = 0.0
            margin_dict = {lbl: 0.0 for lbl in self.LABELS}

        # --- Calibrated probabilities (approximate) -----------------------
        if self.calibrated_pipeline is not None:
            try:
                proba_array = self.calibrated_pipeline.predict_proba([text])[0]
                cal_classes = list(self.calibrated_pipeline.classes_)
                proba_dict = {cls: float(p) for cls, p in zip(cal_classes, proba_array)}
                for lbl in self.LABELS:
                    proba_dict.setdefault(lbl, 0.0)
                confidence = proba_dict.get(predicted_label, 0.0)
            except Exception:
                proba_dict, confidence = self._margins_to_proba(margin_dict, predicted_label)
        else:
            proba_dict, confidence = self._margins_to_proba(margin_dict, predicted_label)

        # Ensure all four labels present.
        for lbl in self.LABELS:
            proba_dict.setdefault(lbl, 0.0)

        return {
            "label": predicted_label,
            "confidence": round(confidence, 4),
            "probabilities": {lbl: round(proba_dict[lbl], 4) for lbl in self.LABELS},
            "margin_score": round(margin_score, 4),
            "estimator": "LinearSVC",
        }

    def predict_with_margins(self, text: str) -> Dict:
        """
        Returns the raw LinearSVC decision margins for each class.
        These are NOT probabilities; a larger positive margin means higher
        confidence in that class for multi-class one-vs-rest LinearSVC.
        """
        if self.pipeline is None:
            return {lbl: 0.0 for lbl in self.LABELS}
        clf_step = self.pipeline.named_steps["clf"]
        classes = list(clf_step.classes_)
        try:
            decision = self.pipeline.decision_function([text])[0]
            if hasattr(decision, "__iter__"):
                return {cls: round(float(m), 4) for cls, m in zip(classes, decision)}
            return {classes[0]: round(float(decision), 4)}
        except Exception:
            return {lbl: 0.0 for lbl in self.LABELS}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _margins_to_proba(margin_dict: Dict, predicted_label: str):
        """
        Normalise raw margins to a pseudo-probability via softmax.
        Used only when CalibratedClassifierCV is unavailable.
        This is an approximation; do not treat as a true probability.
        """
        values = np.array(list(margin_dict.values()), dtype=float)
        # Softmax
        values -= values.max()
        exp_vals = np.exp(values)
        softmax = exp_vals / exp_vals.sum()
        labels = list(margin_dict.keys())
        proba_dict = {lbl: float(p) for lbl, p in zip(labels, softmax)}
        confidence = proba_dict.get(predicted_label, 0.0)
        return proba_dict, confidence

    def _default_result(self) -> Dict:
        return {
            "label": "PUBLIC",
            "confidence": 0.0,
            "probabilities": {lbl: 0.0 for lbl in self.LABELS},
            "margin_score": 0.0,
            "estimator": "LinearSVC",
        }
