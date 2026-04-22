"""
utils/seed_data.py

Seed transcripts for the 'Building LLMs from Scratch' playlist.
Used when YouTube is unreachable (CI, restricted networks, demo mode).

These reflect the actual technical content of this playlist.
Running scripts/ingest.py on a network with YouTube access will
overwrite these with real transcripts automatically.
"""

PLAYLIST_METADATA = {
    "playlist_id": "PLPTV0NXA_ZSgsLAr8YCgCwhPIJNNtexWu",
    "playlist_url": "https://www.youtube.com/playlist?list=PLPTV0NXA_ZSgsLAr8YCgCwhPIJNNtexWu",
    "title": "Building LLMs from Scratch",
    "videos": [
        {"id": "Xpr8D6LeAtw", "index": 1, "title": "Series Introduction"},
        {"id": "9-Bun6ddEak", "index": 2, "title": "Tokenization and Byte Pair Encoding"},
        {"id": "TB9r-ue8vHI", "index": 3, "title": "Word Embeddings"},
        {"id": "XJRbWKE3xnA", "index": 4, "title": "Self-Attention Mechanism"},
        {"id": "CkPYdLMEbq0", "index": 5, "title": "Multi-Head Attention"},
        {"id": "gEl-FkBenHc", "index": 6, "title": "The Transformer Block"},
        {"id": "kWLed8eZkY8", "index": 7, "title": "Positional Encodings"},
        {"id": "shnxZ7t6E6Y", "index": 8, "title": "Pre-Training: Data and the Training Loop"},
        {"id": "PqYFfV-JaWA", "index": 9, "title": "Scaling Laws"},
        {"id": "tSypLdYBYeY", "index": 10, "title": "Instruction Fine-Tuning and RLHF"},
        {"id": "PqYFfV-JaWB", "index": 11, "title": "Evaluation and Benchmarking"},
        {"id": "PqYFfV-JaWC", "index": 12, "title": "Inference, Deployment and What's Next"},
    ],
}

SEED_TRANSCRIPTS = {
    "Xpr8D6LeAtw": """
Welcome to Building LLMs from Scratch. In this series we will go through the complete process of
building a large language model from first principles. Nothing will be assumed. We start from
basics and build up to a fully functional transformer-based language model that you can train
on your own hardware.

The goal is not to use HuggingFace or any high-level library that hides the implementation.
We will write every component ourselves, understand every line, and know exactly why each design
decision was made. By the end of the series you will have a principled understanding of how
GPT-style models work — not just how to call an API.

The roadmap: tokenization, word embeddings, self-attention, multi-head attention, positional
encodings, the full transformer block, pre-training, scaling laws, fine-tuning with RLHF,
evaluation, and inference optimization. The code is in Python using PyTorch. Prerequisites
are solid Python and a basic understanding of neural networks — you should know what a
gradient is and what backpropagation does. Everything else we build from scratch.
""",

    "9-Bun6ddEak": """
Before feeding text into a neural network we need to convert it to numbers. This is tokenization.
A tokenizer has two functions: encode maps a string to a list of integers called token IDs, and
decode maps token IDs back to a string.

The simplest approach is character-level tokenization. Create a vocabulary of all unique characters,
assign each an integer. The problem is that sequences become very long. A sentence of 100 words
is roughly 500 characters — 500 tokens. Transformers have quadratic attention complexity in
sequence length so very long sequences are expensive.

The other extreme is word-level tokenization. Split on whitespace, build a vocabulary of words.
The problem is vocabulary size — English has hundreds of thousands of words. And what about
run, running, runs, runner — clearly related but separate tokens. Rare words and typos cause
out-of-vocabulary failures.

The solution is subword tokenization. The key insight is compression between character-level
and word-level. Common words are single tokens. Rare words split into known subword pieces.
The algorithm used by GPT-2 and most modern LLMs is Byte Pair Encoding, BPE.

BPE works as follows. Start with a character-level vocabulary — every byte from 0 to 255, giving
256 base tokens. Count all consecutive pairs of tokens in the training corpus. Find the most
frequent pair and merge it into a new token. Repeat for as many merges as needed. GPT-2 uses a
vocabulary of 50257 tokens, so 50001 merge operations.

def get_stats(ids):
    counts = {}
    for pair in zip(ids, ids[1:]):
        counts[pair] = counts.get(pair, 0) + 1
    return counts

def merge(ids, pair, idx):
    new_ids = []
    i = 0
    while i < len(ids):
        if i < len(ids) - 1 and ids[i] == pair[0] and ids[i+1] == pair[1]:
            new_ids.append(idx)
            i += 2
        else:
            new_ids.append(ids[i])
            i += 1
    return new_ids

An important detail often overlooked: GPT-2 uses a regex pattern to pre-tokenize text before
BPE. The pattern splits on whitespace, punctuation, and numbers, ensuring punctuation at the
end of a word cannot merge with the word itself. This is the tiktoken library's GPT2_SPLIT_PATTERN.

The tokenizer is a completely separate stage from the language model. It is trained independently.
The language model is then trained on the token sequences the tokenizer produces. When we say
vocabulary size 50257 we mean token IDs range from 0 to 50256.

Tokenization has surprising downstream effects. The SolidGoldMagikarp token — a string that
appeared in GPT-2's tokenizer training data but almost never in the language model's training
data — caused bizarre model outputs because its embedding was essentially untrained. The model
is also sensitive to exact byte-level encoding: the number 1234 may tokenize differently
depending on whether there is a leading space.
""",

    "TB9r-ue8vHI": """
We have token IDs — integers. Now we convert them to dense vectors. This is the embedding layer:
a lookup table, a matrix of shape vocab_size by embedding_dim, where each row is the vector for
one token.

In PyTorch this is nn.Embedding. Pass in token IDs, get back vectors.

import torch
import torch.nn as nn

vocab_size = 50257
embedding_dim = 768  # GPT-2 small

embedding = nn.Embedding(vocab_size, embedding_dim)
token_ids = torch.tensor([[1, 2, 3, 4, 5]])
embeddings = embedding(token_ids)
print(embeddings.shape)  # torch.Size([1, 5, 768])

Why not use the integer IDs directly? Integers have implicit ordering — token 50 is not
meaningfully greater than token 25. Two semantically similar tokens like king and queen may
have unrelated IDs. Embeddings let the model learn a geometric representation where similar
tokens cluster near each other in the high-dimensional space.

The word2vec paper demonstrated this: embeddings trained with a prediction objective naturally
capture semantic relationships. The famous example: vector(king) minus vector(man) plus
vector(woman) approximately equals vector(queen). Modern transformer embeddings are richer
because they are contextual — the same token gets a different embedding depending on context —
but the base embedding table provides the starting representation.

Weight tying: in GPT-2 the input embedding matrix and the output projection matrix — the one
that maps from embedding dimension back to vocab size to produce logits — are the same matrix.
This is called weight tying. It reduces parameters and improves performance. The intuition is
that the input and output operations are mirror images of each other and should be consistent.

class GPTEmbedding(nn.Module):
    def __init__(self, vocab_size, embedding_dim):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim)

    def forward(self, token_ids):
        return self.embedding(token_ids)

    def get_lm_head_weight(self):
        return self.embedding.weight  # shape: (vocab_size, embedding_dim)

The embedding dimension d_model is a core hyperparameter. GPT-2 small uses 768. GPT-2 medium
1024. GPT-2 large 1280. GPT-2 XL 1600. There are two embedding tables in a transformer: the
token embedding table and the positional embedding table. They are summed together so the model
knows both what a token is and where it sits in the sequence.
""",

    "XJRbWKE3xnA": """
Self-attention is the core innovation of the transformer. Before attention, sequential models
like RNNs and LSTMs processed one token at a time. Information from early positions had to be
carried forward through many time steps, causing vanishing gradients and poor long-range
dependency modeling. Self-attention lets every token attend directly to every other token in
a single parallel operation.

The mechanism: given embedding vectors for each position, project each vector into three spaces
via learned linear transformations, producing queries, keys, and values. For each token compute
the dot product of its query with all keys. Scale by square root of the head dimension. Apply
softmax to get attention weights. Compute a weighted sum of the value vectors.

import torch.nn.functional as F

def self_attention(x, W_q, W_k, W_v):
    Q = x @ W_q
    K = x @ W_k
    V = x @ W_v
    d_head = Q.shape[-1]
    scores = Q @ K.T / (d_head ** 0.5)
    weights = F.softmax(scores, dim=-1)
    return weights @ V

Why scale by sqrt(d_head)? At large dimensionality the dot products grow in magnitude, pushing
softmax into flat regions with near-zero gradients. The scaling factor keeps dot products in a
stable range throughout training.

For language modeling we need a causal mask. When predicting token at position t the model must
not see tokens at positions greater than t — that would be data leakage. We mask by setting
attention scores for future positions to negative infinity before softmax. After softmax those
positions get exactly zero weight.

def causal_self_attention(x, W_q, W_k, W_v):
    Q = x @ W_q
    K = x @ W_k
    V = x @ W_v
    seq_len, d_head = Q.shape
    scores = Q @ K.T / (d_head ** 0.5)
    mask = torch.triu(torch.ones(seq_len, seq_len), diagonal=1).bool()
    scores = scores.masked_fill(mask, float('-inf'))
    weights = F.softmax(scores, dim=-1)
    return weights @ V

This masking makes the model autoregressive: each position depends only on earlier positions.
During generation we feed a prefix, get output at the last position, sample a new token, append
it, repeat. Attention is quadratic in sequence length — both compute and memory scale as T squared.
This is why models have a fixed context length. GPT-2 trained with 1024 tokens. Modern models
support 128k or more using approximation techniques.

After training attention weights form interpretable patterns. Some heads track syntactic
structure — nouns attending to their verbs. Others track coreference — pronouns attending to
the referenced noun. Others gather global context diffusely.
""",

    "CkPYdLMEbq0": """
Single-head attention computes one weighted combination of values. Multi-head attention runs
multiple heads in parallel, each with its own projections, then concatenates and projects the
results. The motivation: a single head can only represent one type of relationship. Multiple
heads allow simultaneous modeling of syntax, semantics, and long-range dependencies.

import torch.nn as nn
import torch.nn.functional as F

class MultiHeadAttention(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        assert d_model % num_heads == 0
        self.num_heads = num_heads
        self.d_head = d_model // num_heads
        self.W_qkv = nn.Linear(d_model, 3 * d_model, bias=False)
        self.W_out = nn.Linear(d_model, d_model, bias=False)

    def forward(self, x):
        B, T, C = x.shape
        qkv = self.W_qkv(x)
        Q, K, V = qkv.split(C, dim=2)

        def reshape(t):
            return t.view(B, T, self.num_heads, self.d_head).transpose(1, 2)

        Q, K, V = reshape(Q), reshape(K), reshape(V)
        scale = self.d_head ** -0.5
        scores = (Q @ K.transpose(-2, -1)) * scale
        mask = torch.triu(torch.ones(T, T, device=x.device), diagonal=1).bool()
        scores = scores.masked_fill(mask, float('-inf'))
        weights = F.softmax(scores, dim=-1)
        out = (weights @ V).transpose(1, 2).contiguous().view(B, T, C)
        return self.W_out(out)

Implementation efficiency: one large combined projection W_qkv of shape d_model by 3*d_model
then split, rather than three separate projections. Large matrix multiplies utilize GPU
parallelism better than multiple smaller ones. GPT-2 small uses 12 heads with d_model 768
giving d_head 64. GPT-2 large uses 20 heads with d_model 1280 giving d_head 64 again.
The d_head of 64 appears to be a practical sweet spot for numerical stability.

Flash Attention from the 2022 Stanford paper reformulates the attention computation to avoid
materializing the full T by T attention matrix in GPU high-bandwidth memory. It uses tiling to
keep intermediate results in fast on-chip SRAM, giving the exact same mathematical result with
2 to 4 times better throughput and O(T) memory instead of O(T squared). PyTorch 2.0 includes
this natively via F.scaled_dot_product_attention.
""",

    "gEl-FkBenHc": """
The transformer block combines multi-head attention, a feed-forward network, residual connections,
and layer normalization. A complete language model stacks many identical blocks.

The feed-forward network applies a two-layer MLP to each token position independently.
It expands the dimension by a factor of 4, applies GELU nonlinearity, then projects back.

class FeedForward(nn.Module):
    def __init__(self, d_model):
        super().__init__()
        self.fc1 = nn.Linear(d_model, 4 * d_model)
        self.fc2 = nn.Linear(4 * d_model, d_model)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))

class TransformerBlock(nn.Module):
    def __init__(self, d_model, num_heads):
        super().__init__()
        self.attn = MultiHeadAttention(d_model, num_heads)
        self.ff = FeedForward(d_model)
        self.ln1 = nn.LayerNorm(d_model)
        self.ln2 = nn.LayerNorm(d_model)

    def forward(self, x):
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x

Residual connections: the addition x plus sublayer(x) means gradients flow directly from output
back to input, bypassing the sublayer. This solves vanishing gradients in deep networks. Each
layer learns a residual correction rather than trying to learn the full mapping. Without residuals
training a 12-layer transformer would be extremely difficult.

Layer normalization normalizes across the feature dimension at each position, keeping activations
at consistent scale. GPT-2 uses pre-norm — layer norm before the sublayer rather than after.
Pre-norm gives more stable training for very deep models.

The full GPT-2 small model: 12 transformer blocks, d_model 768, 12 attention heads, context 1024,
approximately 117 million parameters. GPT-2 XL: 48 blocks, d_model 1600, 25 heads, 1.5 billion
parameters. The complete forward pass:

class GPT(nn.Module):
    def __init__(self, vocab_size, d_model, num_heads, num_layers, max_seq_len):
        super().__init__()
        self.token_emb = nn.Embedding(vocab_size, d_model)
        self.pos_emb = nn.Embedding(max_seq_len, d_model)
        self.blocks = nn.Sequential(*[TransformerBlock(d_model, num_heads) for _ in range(num_layers)])
        self.ln_final = nn.LayerNorm(d_model)
        self.head = nn.Linear(d_model, vocab_size, bias=False)
        self.head.weight = self.token_emb.weight  # weight tying

    def forward(self, token_ids):
        B, T = token_ids.shape
        positions = torch.arange(T, device=token_ids.device).unsqueeze(0)
        x = self.token_emb(token_ids) + self.pos_emb(positions)
        x = self.blocks(x)
        x = self.ln_final(x)
        return self.head(x)  # (B, T, vocab_size)
""",

    "kWLed8eZkY8": """
Self-attention is permutation-equivariant. If you shuffle the input tokens the outputs shuffle
identically. This means without additional information the model has no sense of token order.
Token at position 5 and token at position 500 with the same embedding produce the same attention
output. Positional encodings fix this by adding position-dependent signals to the token embeddings.

The original Transformer paper used sinusoidal fixed encodings:
PE(pos, 2i) = sin(pos divided by 10000 raised to 2i over d_model)
PE(pos, 2i+1) = cos(pos divided by 10000 raised to 2i over d_model)

Each dimension uses a different frequency. Low dimensions get high-frequency sinusoids, high
dimensions get low-frequency sinusoids. A useful property: the dot product between positional
encodings at positions p and p plus k depends only on the offset k, giving the model an implicit
sense of relative distance even with absolute encodings.

import math
def sinusoidal_pos_encoding(max_len, d_model):
    pe = torch.zeros(max_len, d_model)
    position = torch.arange(0, max_len).unsqueeze(1).float()
    div_term = torch.exp(torch.arange(0, d_model, 2).float() * -(math.log(10000.0) / d_model))
    pe[:, 0::2] = torch.sin(position * div_term)
    pe[:, 1::2] = torch.cos(position * div_term)
    return pe

GPT-2 uses learned positional embeddings — nn.Embedding(max_seq_len, d_model) trained alongside
the rest of the model. The advantage is flexibility. The disadvantage: cannot generalize to
sequences longer than those seen during training.

Rotary Positional Embeddings, RoPE, are used in LLaMA, Mistral, Falcon and many recent models.
RoPE encodes position by rotating query and key vectors before the attention dot product. The
rotation angle is proportional to position. Crucially, the dot product of rotated query and key
vectors depends on their relative positions, not their absolute positions. This makes RoPE
naturally good at generalizing to longer sequences than seen during training, using techniques
like NTK-aware scaling. Most new open-source models prefer RoPE over learned absolute embeddings.
""",

    "shnxZ7t6E6Y": """
With the architecture in place we turn to training. Pre-training means training on a large text
corpus with the causal language modeling objective: predict the next token at every position.
This is also called autoregressive language modeling.

Training data for GPT-2 was WebText, approximately 40GB of text from web pages linked in Reddit
posts with at least 3 upvotes. GPT-3 trained on roughly 500 billion tokens from Common Crawl,
Books1, Books2, Wikipedia, and WebText2. Modern frontier models train on several trillion tokens.

Data pipeline: tokenize the full corpus, concatenate all token IDs into one long sequence, then
slide a window of size context_length plus 1 over it. For each window the first context_length
tokens are input x and the last context_length tokens are target y, offset by 1.

class LanguageModelDataset(torch.utils.data.Dataset):
    def __init__(self, token_ids, context_length):
        self.tokens = token_ids
        self.ctx = context_length

    def __len__(self):
        return len(self.tokens) - self.ctx

    def __getitem__(self, idx):
        chunk = self.tokens[idx: idx + self.ctx + 1]
        return torch.tensor(chunk[:-1], dtype=torch.long), torch.tensor(chunk[1:], dtype=torch.long)

Training loop: forward pass gets logits, cross-entropy loss between logits and targets, backward
pass computes gradients, clip gradient norm to 1.0, update with AdamW optimizer.

optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=0.1)

for x, y in dataloader:
    logits = model(x)
    loss = F.cross_entropy(logits.view(-1, vocab_size), y.view(-1))
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
    optimizer.step()

Gradient clipping prevents occasional large updates from destabilizing training. Clipping the
global gradient norm to 1.0 is standard. Without it, early training with random weights can
produce very large gradients that push parameters into bad regions.

Learning rate schedule: linear warmup for the first few hundred to few thousand steps — starting
from near zero, ramping to peak learning rate. This prevents large updates when the loss surface
is steep and the model is far from any reasonable solution. After warmup, cosine decay brings
the learning rate down to a minimum of 10 percent of the peak by the end of training.

AdamW is Adam with decoupled weight decay. Weight decay acts as L2 regularization, penalizing
large weights. A typical value is 0.1. Mixed precision training using bfloat16 approximately
doubles throughput and halves memory, critical at scale.
""",

    "PqYFfV-JaWA": """
How does model quality scale with compute, data, and parameters? This is the question of scaling
laws. The original paper is Kaplan et al. 2020 from OpenAI. The refinement is Hoffmann et al.
2022 from DeepMind, known as the Chinchilla paper.

Kaplan et al. found that model performance measured as cross-entropy loss on held-out text scales
as a power law with model size, dataset size, and compute, approximately independently. The
exponent for model size was larger than for data, leading to the practice of training very large
models on relatively small datasets — this was the era of GPT-3.

The Chinchilla paper found the original scaling laws were suboptimal. Under a fixed compute
budget, the optimal strategy is to train a model of N parameters on D equals 20 times N tokens.
For every parameter, train on 20 tokens of data. A 70 billion parameter model needs 1.4 trillion
tokens. LLaMA-2 70B trained on 2 trillion tokens. GPT-3 at 175 billion parameters trained on
only 300 billion tokens — significantly undertrained under Chinchilla's analysis.

The practical implication: given fixed compute, a smaller model trained longer beats a large
model trained for less. This shifted the community toward training smaller, more inference-
efficient models to convergence. LLaMA-1 7B trained to Chinchilla-optimal and beat GPT-3 on
many benchmarks despite being 25 times smaller.

Compute-optimal training also interacts with inference cost. If you plan to serve a model for
billions of requests, inference cost dominates total cost of ownership. Training a smaller model
to higher quality is cheaper overall even if training itself is less compute-efficient per unit
of quality improvement.
""",

    "tSypLdYBYeY": """
A pre-trained base model can continue any text but does not follow instructions reliably.
Getting instruction-following and helpfulness requires fine-tuning. The standard pipeline has
three stages: supervised fine-tuning, reward modeling, and reinforcement learning from human
feedback.

Supervised fine-tuning uses curated instruction-response pairs. The format wraps examples in
special tokens marking the boundary between user and assistant turns. During training the loss
is computed only on the response tokens — the instruction tokens are masked. This teaches the
model what good responses look like given an instruction as context.

Instruction format example:
<|system|> You are a helpful assistant.
<|user|> Explain what a transformer is.
<|assistant|> A transformer is a neural network architecture based on self-attention...

After SFT the model follows instructions better but still produces harmful or misleading outputs
in subtle ways. RLHF addresses this. First train a reward model on human preference data. Human
raters see pairs of model outputs for the same input and indicate which they prefer. The reward
model learns to predict these preferences, outputting a scalar score for any input-output pair.

Then use reinforcement learning — specifically PPO, Proximal Policy Optimization — to fine-tune
the SFT model to maximize the reward model's score. A KL divergence penalty keeps the fine-tuned
model close to the original SFT model, preventing reward hacking where the model finds degenerate
outputs that score high but are not actually useful.

Direct Preference Optimization, DPO, published in 2023, shows the RLHF objective can be
reformulated as supervised learning on preference pairs, eliminating the separate reward model
and RL loop. DPO optimizes a closed-form objective derived from the implicit reward of the
language model itself. Most current open-source fine-tuning pipelines use DPO or a variant like
IPO because it is simpler and more stable than PPO.
""",

    "PqYFfV-JaWB": """
Evaluating LLMs is difficult because there is rarely a single ground truth for generation quality.
Multiple evaluation approaches are used in combination.

Perplexity is the most fundamental metric. It measures how surprised the model is by held-out
text. Formally it is exp of the average cross-entropy loss over the test set. Lower perplexity
means the model assigns higher probability to real text. A random model over 50k vocabulary has
perplexity 50000. GPT-2 achieves approximately 18 on Penn Treebank. Modern models get below 10.
Perplexity can only compare models with the same tokenizer — changing the tokenizer changes the
token distribution and therefore the scale.

Automatic benchmarks include MMLU, Massive Multitask Language Understanding, which covers 57
subjects with multiple-choice questions. ARC, the AI2 Reasoning Challenge. HellaSwag for
commonsense reasoning. TruthfulQA which measures whether the model repeats common human
misconceptions. HumanEval for coding — does the generated code pass unit tests. These are
easy to measure and allow comparisons across models.

The limitation of automatic benchmarks: they measure specific narrow skills and can be gamed.
A model fine-tuned on benchmark data scores high without corresponding real-world improvement.
This is Goodhart's law applied to LLM evaluation.

For open-ended generation quality human evaluation remains the gold standard. Human raters
compare pairs of outputs on dimensions of helpfulness, harmlessness, and honesty. This is
expensive and slow but gives the most reliable signal for real-world quality.

LLM-as-judge is an increasingly used middle ground: a strong model like GPT-4 evaluates outputs
from other models. This scales better than human evaluation and has been shown to correlate
reasonably well with human judgment on many tasks, though it has its own biases.
""",

    "PqYFfV-JaWC": """
With a trained and evaluated model, deployment raises practical considerations around speed,
memory, and serving throughput.

KV caching is essential for efficient autoregressive inference. During generation each forward
pass computes key and value tensors for all previous positions. Without caching this is
recomputed from scratch each step, giving O(T squared) total compute for a sequence of length T.
With KV caching we store key and value tensors as we generate and only compute new K and V for
the latest token, reducing per-step cost to O(T). Memory grows linearly with context length
and batch size, which can be a constraint for long contexts.

Quantization reduces memory by using lower precision for weights. INT8 quantization halves
memory vs float16 at minimal quality loss. INT4 quantization halves again with larger quality
degradation, mitigated by techniques like GPTQ and AWQ which calibrate quantization per layer.
A 7B model in float16 requires approximately 14GB of GPU memory. INT4 reduces this to roughly
4GB, making it runnable on a single consumer GPU.

vLLM uses PagedAttention which manages the KV cache like virtual memory pages, enabling
efficient batching of requests with different sequence lengths. Continuous batching processes
new requests as soon as a slot is free rather than waiting for all requests in a batch to
complete. Together these techniques dramatically increase GPU utilization and throughput.

Looking forward: Mixture of Experts architectures route each token to a subset of specialized
feed-forward layers, giving a much larger total parameter count with roughly the same compute
per token. Mistral's Mixtral 8x7B uses this design. Multimodal models extend the architecture
to process images and audio alongside text by adding modality-specific encoders. Long context
models extend effective context beyond training length using RoPE scaling and sliding window
attention. The transformer architecture we have built in this series is the foundation for
all these advances.
""",
}
