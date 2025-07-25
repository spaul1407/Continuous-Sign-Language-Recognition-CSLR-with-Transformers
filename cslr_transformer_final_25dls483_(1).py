# -*- coding: utf-8 -*-
"""CSLR_Transformer_Final_25DLS483 (1).ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1M_PP7a_R4_xyt3Huwl3eQhUcY7BVbjQE
"""

!pip install -q kaggle
import os
os.environ['KAGGLE_CONFIG_DIR'] = './content'
os.environ['KAGGLEHUB_CACHE'] = './content'

import kagglehub
path = kagglehub.dataset_download("drblack00/isl-csltr-indian-sign-language-dataset")

print("Path to dataset files:", path)
if(path=='/kaggle/input/isl-csltr-indian-sign-language-dataset'):
   !cp -r /kaggle/input/isl-csltr-indian-sign-language-dataset/ISL_CSLRT_Corpus/ISL_CSLRT_Corpus /content
else:
   !cp -r /content/content/datasets/drblack00/isl-csltr-indian-sign-language-dataset/versions/1/ISL_CSLRT_Corpus/ISL_CSLRT_Corpus /content

import pandas as pd

read_file = pd.read_excel ("/content/ISL_CSLRT_Corpus/corpus_csv_files/ISL_CSLRT_Corpus_frame_details.xlsx")

read_file.to_csv ("ISL_CSLRT_Corpus_frame_details.csv",
                  index = None,
                  header=True)

!pip uninstall -y torch torchvision torchtext torchaudio jiwer numpy -q
!pip install -q torch==2.1.0 torchvision==0.16.0 torchtext==0.16.0 torchaudio==2.1.0
!pip install numpy==1.26.4

import os
import torch
import torchvision.transforms as transforms
from torchvision.models import resnet18
from PIL import Image
import torchtext
from torchtext.vocab import build_vocab_from_iterator
from torch.nn.utils.rnn import pad_sequence
import pandas as pd


device='cuda' if torch.cuda.is_available() else 'cpu'
device

resnet = resnet18(pretrained=True)
resnet = torch.nn.Sequential(*list(resnet.children())[:-1])
resnet.eval()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def extract_features_from_folder(frame_folder):
    features = []
    for frame_name in sorted(os.listdir(frame_folder)):
        img_path = os.path.join(frame_folder, frame_name)
        image = Image.open(img_path).convert("RGB")
        image_tensor = transform(image).unsqueeze(0)
        with torch.no_grad():
            feature = resnet(image_tensor).squeeze()
        features.append(feature)
    return torch.stack(features)

import torchtext
from torchtext.vocab import build_vocab_from_iterator
from torch.nn.utils.rnn import pad_sequence
import pandas as pd
import torch

df = pd.read_csv('/content/ISL_CSLRT_Corpus_frame_details.csv')
sentences = df['Sentence'].tolist()

def yield_tokens(sentences):
    for sentence in sentences:
        yield sentence.lower().split()

vocab = build_vocab_from_iterator(yield_tokens(sentences), specials=["<pad>", "<sos>", "<eos>", "<unk>"])
vocab.set_default_index(vocab["<unk>"])

from torch.utils.data import Dataset, DataLoader

class CSLRDataset(Dataset):
  def __init__(self, df, vocab, frame_path_base, max_text_len=100, transform=None):
      self.df = df.reset_index(drop=True)
      self.vocab = vocab
      self.frame_path_base = frame_path_base
      self.max_text_len = max_text_len
      self.transform = transform or transforms.Compose([
          transforms.Resize((128, 128)),
          transforms.ToTensor()
      ])

  def __len__(self):
        return len(self.df)

  def __getitem__(self, idx):
    row = self.df.iloc[idx]
    sentence = row['Sentence']

    raw_path = row['Frames path'].replace("\\", "/").strip()

    cleaned_parts = [part.strip() for part in raw_path.split("/")]
    cleaned_path = os.path.join("/content", *cleaned_parts)
    if not os.path.exists(cleaned_path):
      print("Missing file:", cleaned_path)


    image = Image.open(cleaned_path).convert("RGB")
    image = self.transform(image)


    tokens = sentence.lower().split()

    tokens = ["<sos>"] + tokens + ["<eos>"]
    encoded = self.vocab.lookup_indices(tokens)


    if len(encoded) < self.max_text_len:

        padding = [self.vocab["<pad>"]] * (self.max_text_len - len(encoded))
        encoded += padding
        attention_mask = [1] * len(tokens) + [0] * len(padding)
    else:

        encoded = encoded[:self.max_text_len]
        attention_mask = [1] * self.max_text_len

    encoded = torch.tensor(encoded, dtype=torch.long)
    attention_mask = torch.tensor(attention_mask, dtype=torch.long)


    return {
        "video": image.unsqueeze(0),
        "input_ids": encoded,
        "attention_mask": attention_mask,
        "sentence": sentence
    }






def collate_fn(batch):
    """
    Pads a batch of video tensors and tokenized text inputs for CSLR.
    Each item in the batch is a dictionary from the dataset's __getitem__.
    """
    from torch.nn.utils.rnn import pad_sequence


    videos = [item['video'] for item in batch]
    input_ids = [item['input_ids'] for item in batch]
    attention_masks = [item['attention_mask'] for item in batch]
    sentences = [item['sentence'] for item in batch]


    videos = torch.stack(videos)


    input_ids_padded = pad_sequence(input_ids, batch_first=True, padding_value=vocab["<pad>"])
    attention_masks_padded = pad_sequence(attention_masks, batch_first=True, padding_value=0)

    return {
        'video': videos,
        'input_ids': input_ids_padded,
        'attention_mask': attention_masks_padded,
        'sentences': sentences
    }

from sklearn.model_selection import train_test_split

import numpy as np

df_trainval, df_test = train_test_split(df, test_size=0.1, random_state=42, shuffle=True)
df_train, df_val = train_test_split(df_trainval, test_size=0.1, random_state=42, shuffle=True)

train_dataset = CSLRDataset(df_train, vocab, "/content/ISL_CSLRT_Corpus/Frames_Sentence_Level")
val_dataset   = CSLRDataset(df_val, vocab, "/content/ISL_CSLRT_Corpus/Frames_Sentence_Level")
test_dataset  = CSLRDataset(df_test, vocab, "/content/ISL_CSLRT_Corpus/Frames_Sentence_Level")


train_loader = DataLoader(train_dataset, batch_size=8, shuffle=True, collate_fn=collate_fn)
val_loader   = DataLoader(val_dataset, batch_size=8, shuffle=False, collate_fn=collate_fn)
test_loader  = DataLoader(test_dataset, batch_size=8, shuffle=False, collate_fn=collate_fn)

import torch.nn as nn
class LearnablePositionalEncoding(nn.Module):
    def __init__(self, max_len, d_model):
        super().__init__()
        self.pos_embedding = nn.Embedding(max_len, d_model)

    def forward(self, x):
        positions = torch.arange(0, x.size(1), device=x.device).unsqueeze(0)
        return x + self.pos_embedding(positions)

import torch.nn as nn
import torch.nn.functional as F

class TransformerCSLR(nn.Module):
    def __init__(self, feature_dim, vocab_size, d_model=512, nhead=8, num_layers=4):
        super().__init__()
        self.input_fc = nn.Linear(feature_dim, d_model)
        self.pos_encoder = LearnablePositionalEncoding(max_len=500, d_model=d_model)
        self.transformer = nn.Transformer(d_model=d_model, nhead=nhead,
                                          num_encoder_layers=num_layers,
                                          num_decoder_layers=num_layers,
                                          dim_feedforward=2048,
                                          dropout=0.1,
                                          batch_first=False,
                                          norm_first=True)
        self.embedding = nn.Embedding(vocab_size, d_model)
        self.out_fc = nn.Linear(d_model, vocab_size)

        self.generator = nn.Linear(d_model, vocab_size)
        self.sos_idx = vocab["<sos>"]
        self.eos_idx = vocab["<eos>"]

    def forward(self, src, tgt):
        src = self.input_fc(src)
        src = src.permute(1, 0, 2)

        tgt_emb = self.embedding(tgt)

        positions = torch.arange(0, tgt.size(1)).unsqueeze(0).repeat(tgt.size(0), 1).to(tgt.device)
        tgt_emb = self.pos_encoder(tgt_emb)
        tgt_emb = tgt_emb.permute(1, 0, 2)


        tgt_mask = self.transformer.generate_square_subsequent_mask(tgt.size(1)).to(tgt.device)

        out = self.transformer(src, tgt_emb, tgt_mask=tgt_mask)
        out = out.permute(1, 0, 2)
        return self.out_fc(out)

    def generate_square_subsequent_mask(self, sz):
        """Generates an upper-triangular matrix of -inf, with 0s on diagonal."""
        mask = (torch.triu(torch.ones(sz, sz)) == 1).transpose(0, 1)
        mask = mask.float().masked_fill(mask == 0, float('-inf')).masked_fill(mask == 1, float(0.0))
        return mask

    def generate(self, src, beam_width=3, max_len=30, sos_token=1, eos_token=2):
      self.eval()
      batch_size = src.size(0)


      src = self.input_fc(src)
      src = src.permute(1, 0, 2)
      memory = self.transformer.encoder(src)

      sequences = [[{'tokens': [sos_token], 'score': 0.0}] for _ in range(batch_size)]

      for _ in range(max_len):
          all_completed = True
          for b in range(batch_size):
              current_seqs = [seq for seq in sequences[b] if seq['tokens'][-1] != eos_token]
              if not current_seqs:
                  continue

              all_completed = False
              candidates = []
              for seq in current_seqs:
                  tgt_input = torch.tensor(seq['tokens'], dtype=torch.long).unsqueeze(0).to(src.device)


                  tgt_emb = self.embedding(tgt_input)
                  positions = torch.arange(0, tgt_input.size(1)).unsqueeze(0).to(tgt_input.device)
                  tgt_emb = tgt_emb + self.pos_encoder(positions)

                  tgt_emb = tgt_emb.permute(1, 0, 2)

                  tgt_mask = self.generate_square_subsequent_mask(tgt_emb.size(0)).to(src.device)

                  decoder_output = self.transformer.decoder(
                      tgt_emb, memory[:, b:b+1, :], tgt_mask=tgt_mask
                  )

                  logits = self.generator(decoder_output[-1, 0])
                  probs = F.log_softmax(logits, dim=-1)

                  topk = torch.topk(probs, beam_width)
                  for i in range(beam_width):
                      next_token = topk.indices[i].item()
                      new_score = seq['score'] + topk.values[i].item()
                      new_seq = {'tokens': seq['tokens'] + [next_token], 'score': new_score}
                      candidates.append(new_seq)


              completed = [seq for seq in sequences[b] if seq['tokens'][-1] == eos_token]
              sequences[b] = sorted(candidates + completed, key=lambda x: x['score'], reverse=True)[:beam_width]

          if all_completed:
              break


      best_seqs = [sorted(seqs, key=lambda x: x['score'], reverse=True)[0]['tokens'] for seqs in sequences]


      padded = torch.nn.utils.rnn.pad_sequence(
          [torch.tensor(seq, dtype=torch.long) for seq in best_seqs],
          batch_first=True,
          padding_value=0
      )
      return padded

!pip install -q numpy
from torch.optim import lr_scheduler
import torch.nn.functional as F
from tqdm import tqdm
import numpy

model = TransformerCSLR(512, len(vocab)).to(device)
resnet = resnet.to(device)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=15)
loss_fn = nn.CrossEntropyLoss(ignore_index=vocab["<pad>"])

for epoch in range(15):
    model.train()
    total_loss = 0
    for batch in tqdm(train_loader):
        src = batch['video'].to(device)
        tgt = batch['input_ids'].to(device)
        src = src[:, 0, :, :, :]
        with torch.no_grad():
            src_features = resnet(src).squeeze()
        tgt_input = tgt[:, :-1]
        tgt_output = tgt[:, 1:]

        logits = model(src_features.unsqueeze(1), tgt_input)
        logits = logits.reshape(-1, logits.shape[-1])
        tgt_output = tgt_output.reshape(-1)

        loss = loss_fn(logits, tgt_output)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    scheduler.step()

    print(f"Epoch {epoch}, Loss: {total_loss / len(train_loader)}")

!pip install jiwer -q
import jiwer
import torch
from tqdm import tqdm
import matplotlib.pyplot as plt
import inspect

def evaluate_wer(model, loader, vocab, resnet_model, device="cuda"):
    model.eval()
    resnet_model.eval()
    wers = []

    with torch.no_grad():
        for batch in loader:
            video_inputs = batch['video'].to(device)
            targets = batch['input_ids'].tolist()


            video_inputs = video_inputs.squeeze(1)
            video_features = resnet_model(video_inputs).squeeze()
            video_features = video_features.unsqueeze(1)


            preds = model.generate(video_features, beam_width=3)

            for pred_seq, target_seq in zip(preds, targets):

                hyp = " ".join([vocab.lookup_token(token_id) for token_id in pred_seq if token_id not in [vocab["<pad>"], vocab["<sos>"], vocab["<eos>"], vocab["<unk>"]]])
                ref = " ".join([vocab.lookup_token(token_id) for token_id in target_seq if token_id not in [vocab["<pad>"], vocab["<sos>"], vocab["<eos>"], vocab["<unk>"]]])

                if ref and hyp:
                    wers.append(jiwer.wer(ref, hyp))
                else:
                    wers.append(1.0)

    plt.hist(wers, bins=20)
    plt.title("WER Distribution")
    plt.xlabel("WER")
    plt.ylabel("Frequency")
    plt.show()

    return sum(wers) / len(wers) if wers else 0.0


model.to(device)
resnet.to(device)


avg_wer = evaluate_wer(
    model=model,
    loader=test_loader,
    vocab=vocab,
    resnet_model=resnet,
    device=device
)

print(f"Average WER on test set: {avg_wer:.4f}")

# !pip install nltk
# import nltk
# nltk.download('punkt')

# from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction

# def evaluate_bleu(model, loader, vocab, device, max_len=30):
#     model.eval()
#     references = []
#     hypotheses = []

#     with torch.no_grad():
#         for batch in loader:
#             videos = batch['video'].to(device)
#             targets = batch['input_ids'].to(device)

#             videos = videos.squeeze(1) # Remove the sequence length dimension of 1: (B, C, H, W)
#             video_features = resnet(videos).squeeze() # Use the global resnet model
#             video_features = video_features.unsqueeze(1) # Shape: (B, 1, 512)

#             preds = model.generate(video_features, max_len=max_len)

#             for pred_seq, target_seq in zip(preds, targets):
#                 pred_tokens = [vocab.lookup_token(idx.item()) for idx in pred_seq if idx.item() not in [vocab["<sos>"], vocab["<eos>"], vocab["<pad>"]]]
#                 target_tokens = [vocab.lookup_token(idx.item()) for idx in target_seq if idx.item() not in [vocab["<sos>"], vocab["<eos>"], vocab["<pad>"]]]

#                 hypotheses.append(pred_tokens)
#                 references.append([target_tokens])  # BLEU expects a list of references

#     smoothie = SmoothingFunction().method4

#     bleu1 = [sentence_bleu(ref, hyp, weights=(1, 0, 0, 0), smoothing_function=smoothie) for ref, hyp in zip(references, hypotheses)]
#     bleu2 = [sentence_bleu(ref, hyp, weights=(0.5, 0.5, 0, 0), smoothing_function=smoothie) for ref, hyp in zip(references, hypotheses)]
#     bleu3 = [sentence_bleu(ref, hyp, weights=(0.33, 0.33, 0.33, 0), smoothing_function=smoothie) for ref, hyp in zip(references, hypotheses)]
#     bleu4 = [sentence_bleu(ref, hyp, weights=(0.25, 0.25, 0.25, 0.25), smoothing_function=smoothie) for ref, hyp in zip(references, hypotheses)]

#     print(f"BLEU-1: {sum(bleu1)/len(bleu1) * 100:.2f}")
#     print(f"BLEU-2: {sum(bleu2)/len(bleu2) * 100:.2f}")
#     print(f"BLEU-3: {sum(bleu3)/len(bleu3) * 100:.2f}")
#     print(f"BLEU-4: {sum(bleu4)/len(bleu4) * 100:.2f}")

#     return {
#         "BLEU-1": sum(bleu1)/len(bleu1),
#         "BLEU-2": sum(bleu2)/len(bleu2),
#         "BLEU-3": sum(bleu3)/len(bleu3),
#         "BLEU-4": sum(bleu4)/len(bleu4),
#     }
# evaluate_bleu(model, test_loader, vocab, device)

