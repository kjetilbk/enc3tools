import argparse
import numpy as np
import math
import sys

def read_word_vectors(filename):
    with open(filename, 'r') as f:
        words = [x.rstrip().split(' ')[0] for x in f.readlines()]
    with open(filename, 'r') as f:
        vectors = {}
        for line in f:
            vals = line.rstrip().split(' ')
            vectors[vals[0]] = map(float, vals[1:])

    vocab_size = len(words)
    vocab = {w: idx for idx, w in enumerate(words)}
    ivocab = {idx: w for idx, w in enumerate(words)}

    vector_dim = len(vectors[ivocab[0]])
    W = np.zeros((vocab_size, vector_dim))
    for word, v in vectors.iteritems():
        if word == '<unk>':
            continue
        W[vocab[word], :] = v

    # normalize each word vector to unit variance                                                                                              
    W_norm = np.zeros(W.shape)
    d = (np.sum(W ** 2, 0) ** (0.5))
    W_norm = (W / d)
    #print "Glove:"
    vectors = {}
    for word in words:
        vectors[word] = W_norm[vocab[word]]
    return vectors
