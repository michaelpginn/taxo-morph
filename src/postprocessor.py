"""Masked language model trained on output sequences used to correct missing glosses"""

import click
import wandb
import torch
import math
from transformers import RobertaConfig, TrainingArguments, Trainer, RobertaForMaskedLM
from datasets import DatasetDict
from data import prepare_dataset, load_data_file
from encoder import CustomEncoder, create_vocab
import random

device = "cuda:0" if torch.cuda.is_available() else "cpu"


@click.command()
@click.option("--seed", help="Random seed", type=int)
def train(seed):
    MODEL_INPUT_LENGTH = 64
    BATCH_SIZE = 64
    EPOCHS = 100

    wandb.init(project="taxo-morph-postprocessor", entity="michael-ginn", config={
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "random-seed": seed,
    })

    random.seed(seed)

    train_data = load_data_file(f"../data/usp-train-track2-uncovered")
    dev_data = load_data_file(f"../data/usp-dev-track2-uncovered")

    print("Preparing datasets...")

    train_vocab = create_vocab([line.morphemes() for line in train_data], threshold=1)
    encoder = CustomEncoder(vocabulary=train_vocab)

    dataset = DatasetDict()
    dataset['train'] = prepare_dataset(data=train_data, encoder=encoder, model_input_length=MODEL_INPUT_LENGTH, device=device)
    dataset['dev'] = prepare_dataset(data=dev_data, encoder=encoder, model_input_length=MODEL_INPUT_LENGTH, device=device)

    if arch_size == 'full':
        config = RobertaConfig(
            vocab_size=encoder.vocab_size(),
            max_position_embeddings=MODEL_INPUT_LENGTH,
            pad_token_id=encoder.PAD_ID,
        )
    else:
        config = RobertaConfig(
            vocab_size=encoder.vocab_size(),
            max_position_embeddings=MODEL_INPUT_LENGTH,
            pad_token_id=encoder.PAD_ID,
            num_hidden_layers=3,
            hidden_size=100,
            num_attention_heads=5
        )
    language_model = RobertaForMaskedLM(config=config)

    args = TrainingArguments(
        output_dir=f"../training-checkpoints",
        evaluation_strategy="epoch",
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=3,
        weight_decay=0.01,
        save_strategy="epoch",
        save_total_limit=3,
        num_train_epochs=EPOCHS,
        report_to="wandb",
    )
    trainer = Trainer(
        model=language_model,
        args=args,
        train_dataset=dataset['train'],
        eval_dataset=dataset['dev']
    )

    trainer.train()
    eval_results = trainer.evaluate()
    print(f"Perplexity: {math.exp(eval_results['eval_loss']):.2f}")

    trainer.save_model(f'./usp-lang-model')

if __name__ == "__main__":
    train()