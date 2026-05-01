import argparse
import os

import pandas as pd
import torch
from datasets import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

from app.models.vulnerability_model import ModelArtifact


def prepare_dataset(csv_path: str) -> Dataset:
    """Load and normalize the provided CSV into a HuggingFace Dataset.

    This project expects the provided dataset to follow the schema seen in
    `c_secure_compliance_dataset_10k (1).csv` with columns including:
      - `id` (optional)
      - `label` (0 or 1)  <-- target
      - `code` (source code snippet)  <-- text
      - other metadata columns (cwe, standard, rationale, project, ...)

    The function is robust: it will look for common column names and fall back
    to best-effort extraction. It returns a Dataset with columns: `text`,
    `labels`.
    """
    df = pd.read_csv(csv_path)

    # Determine text column: prefer `code`, else try common alternatives
    text_col = None
    for candidate in ["code", "snippet", "source", "text"]:
        if candidate in df.columns:
            text_col = candidate
            break
    if text_col is None:
        # As a last resort, pick the last column (sometimes CSVs put code last)
        text_col = df.columns[-1]

    # Determine label column: prefer `label`, else try `target` or `y`
    label_col = None
    for candidate in ["label", "labels", "target", "y"]:
        if candidate in df.columns:
            label_col = candidate
            break
    if label_col is None:
        raise ValueError(
            "Could not find a label column in the CSV. "
            "Expecting 'label' (0/1)."
        )

    # Ensure labels are binary integers
    df[label_col] = (
        pd.to_numeric(df[label_col], errors='coerce')
        .fillna(0)
        .astype(int)
    )

    # Build DataFrame with required cols
    proc = pd.DataFrame(
        {
            'text': df[text_col].astype(str),
            'labels': df[label_col].astype(int),
        }
    )

    # Create HF Dataset
    ds = Dataset.from_pandas(proc)
    return ds


def tokenize_function(examples, tokenizer):
    """Tokenize a batch of examples; return padded tensors."""
    return tokenizer(
        examples['text'],
        truncation=True,
        padding='max_length',
        max_length=256,
    )


def main():
    """Train the vulnerability model."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--dataset',
        required=False,
        default=os.path.join(
            '..', 'datasets', 'provided_dataset.csv'
        ),
        help='Path to provided dataset CSV',
    )
    parser.add_argument(
        '--output-dir',
        required=False,
        default=os.path.join('models', 'artifacts'),
    )
    parser.add_argument(
        '--model-name', default='microsoft/codebert-base'
    )
    parser.add_argument('--epochs', type=int, default=2)
    parser.add_argument('--batch-size', type=int, default=8)
    args = parser.parse_args()

    # Prepare dataset from CSV
    print(f"Loading dataset from: {args.dataset}")
    ds = prepare_dataset(args.dataset)

    # Prepare tokenizer and tokenize dataset
    tokenizer = AutoTokenizer.from_pretrained(args.model_name)
    ds = ds.map(
        lambda x: tokenize_function(x, tokenizer), batched=True
    )

    # Rename labels column to `labels` (Trainer expects that name)
    if 'labels' not in ds.column_names and 'label' in ds.column_names:
        ds = ds.rename_column('label', 'labels')

    # Select tensor columns
    columns = [
        c
        for c in ['input_ids', 'attention_mask', 'labels']
        if c in ds.column_names
    ]
    ds.set_format(type='torch', columns=columns)

    # Initialize model
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_name, num_labels=2
    )

    # Training arguments - conservative defaults for quick fine-tuning
    training_args = TrainingArguments(
        output_dir=args.output_dir,
        evaluation_strategy='no',
        per_device_train_batch_size=args.batch_size,
        num_train_epochs=args.epochs,
        save_strategy='epoch',
        logging_steps=50,
        fp16=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=ds,
        tokenizer=tokenizer,
    )

    # Launch training
    print("Starting training...")
    trainer.train()
    print("Training complete; saving artifacts...")

    # Ensure output directory exists and save artifacts
    os.makedirs(args.output_dir, exist_ok=True)
    ModelArtifact.save(model, tokenizer, args.output_dir)
    print(f"Model artifacts saved to {args.output_dir}")


if __name__ == '__main__':
    main()
