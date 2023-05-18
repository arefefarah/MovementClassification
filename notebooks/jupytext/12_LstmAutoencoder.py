# ---
# jupyter:
#   jupytext:
#     formats: ipynb,jupytext//py
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.13.7
#   kernelspec:
#     display_name: base
#     language: python
#     name: python3
# ---

# +
import sys
sys.path.insert(0, '../')
import movement_classifier.utils as utils
import movement_classifier.data_loader as data_loader
import movement_classifier.model_funcs as model_funcs
import movement_classifier.gpt_reverse_model as gpt_reverse_model

from os.path import dirname, join as pjoin
import os
import sys
import math

import dlc2kinematics
# from sequitur.models import CONV_LSTM_AE
# from sequitur.models import LSTM_AE 
from sequitur import quick_train
from scipy.interpolate import CubicSpline
import matplotlib.pyplot as plt
from sklearn import preprocessing
import torch.nn as nn
import numpy as np
from torch.nn import MSELoss
from matplotlib import animation
import copy
from IPython.display import HTML
from celluloid import Camera
# %matplotlib inline
import pandas as pd
import plotly.express as px
import torch
import plotly
from sklearn.decomposition import PCA
import seaborn as sns
import scipy.io as sio
# -

"""Load raw data and create Dataframe of all subjects and their movements and save them"""
min_length,max_length,_,_ = data_loader.timelength_loader("../data/01_raw/F_Subjects")
sub_info,movement_name_list,subjects = data_loader.csvSubject_loader("../data/01_raw/CSV_files",min_length,max_length,method="interpolation")
data_loader.save_data(sub_info, movement_name_list,subjects, method = "interpolation")

"""load dataframes for the modelling"""
path_file = "../data/03_processed/interpolation"
data_dict = data_loader.load_data_dict(path_file)
data_dict.keys()
# np.unique(data_dict["labels_name"])
data = data_dict['input_model']
train_input = torch.Tensor(data[0:1050,:,0:633])
#  train_Set should be ==>  [num_examples, seq_len, *num_features]
train_set  = train_input.permute(0,2,1)
train_set.shape
test_input = torch.Tensor(data[1050:1250,:,0:633])
test_set  = test_input.permute(0,2,1)
val_input = torch.Tensor(data[1250:1319,:,0:633])
val_set  = val_input.permute(0,2,1)
val_set.shape


# +
sample = np.array(val_input[0])
sample.shape
fig, axs = plt.subplots(nrows=28, figsize=(5, 30))
data = sample
# plot each row in a separate subplot
for i in range(28):
    axs[i].plot(data[i])
    axs[i].set_title('Row {}'.format(i+1))

# adjust the layout of the subplots
plt.tight_layout()

# show the plot
plt.show()
# -

seq_len, n_features = train_set.shape[1], train_set.shape[2]
seq_len, n_features

# +
# functions:
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Encoder(nn.Module):

  def __init__(self):
    super(Encoder, self).__init__()

    self.lstm1 = nn.LSTM(input_size=28, hidden_size=14, num_layers=1, batch_first=True)
    self.lstm2 = nn.LSTM(input_size=14, hidden_size=7, num_layers=1, batch_first=True)

    

  def forward(self, x):
    x = x.reshape((1,633, 28))
    encoded, _ = self.lstm1(x)
    encoded, _ = self.lstm2(encoded)

    return encoded
  


class Decoder(nn.Module):

  def __init__(self):
    super(Decoder, self).__init__()



    self.lstm1 = nn.LSTM(input_size=7, hidden_size=14, num_layers=1, batch_first=True)
    self.lstm2 = nn.LSTM(input_size=14, hidden_size=28, num_layers=1, batch_first=True)


  def forward(self, x):
 
    decoded, _ = self.lstm1(x)
    decoded, _ = self.lstm2(decoded)

    return( decoded)
  

  

class RecurrentAutoencoder(nn.Module):

  def __init__(self):
    super(RecurrentAutoencoder, self).__init__()

    # print("seq_len ", seq_len, "num of features ", n_features)
    self.encoder = Encoder().to(device)
    self.decoder = Decoder().to(device)

  def forward(self, x):
    x = self.encoder(x)
    # print(x.size, "   x size")
    x = self.decoder(x)

    return x


# +
#  Training

def train_model(model, train_dataset, val_dataset, n_epochs):
  optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
  # or nn.L1loss(reduction = "sum")
  # criterion = nn.L1loss(reduction = "sum").to(device)
  criterion = MSELoss().to(device)
  history = dict(train=[], val=[])

  best_model_wts = copy.deepcopy(model.state_dict())
  best_loss = 10000.0
  
  for epoch in range(1, n_epochs + 1):
    model = model.train()

    train_losses = []
    for seq_true in train_dataset:
      optimizer.zero_grad()

      seq_true = seq_true.to(device)
      seq_pred = model(seq_true)
      # print("#######################",seq_true.shape, "shape true seq ")
      # print("#######################",seq_pred.shape, "shape of output")
      loss = criterion(seq_pred.reshape(633,28), seq_true)

      loss.backward()
      optimizer.step()

      train_losses.append(loss.item())

    val_losses = []
    val_data_predicted = []
    model = model.eval()
    with torch.no_grad():
      for seq_true in val_dataset:

        seq_true = seq_true.to(device)
        seq_pred = model(seq_true)
        val_data_predicted.append(seq_pred.reshape(633,28))
        loss = criterion(seq_pred.reshape(633,28), seq_true)
        val_losses.append(loss.item())

    train_loss = np.mean(train_losses)
    val_loss = np.mean(val_losses)

    history['train'].append(train_loss)
    history['val'].append(val_loss)

    if val_loss < best_loss:
      best_loss = val_loss
      best_model_wts = copy.deepcopy(model.state_dict())

    print(f'Epoch {epoch}: train loss {train_loss} val loss {val_loss}')

  model.load_state_dict(best_model_wts)
  return model.eval(), history,val_data_predicted


# +
model = RecurrentAutoencoder()
model = model.to(device)

model, history, val_data_predicted = train_model(
  model, 
  train_set, 
  val_set, 
  n_epochs=100
)
# -

np.save("../data/03_processed/val_data_predicted.npy", val_data_predicted)

np.save("../data/03_processed/history.npy", history)

# +

sample = val_data_predicted[0]
sample = torch.permute(sample, (1, 0))

fig, axs = plt.subplots(nrows=28, figsize=(8, 40))
data = sample
# plot each row in a separate subplot
for i in range(28):
    axs[i].plot(data[i])
    axs[i].set_title('Row {}'.format(i+1))

# adjust the layout of the subplots
plt.tight_layout()

# show the plot
plt.show()
# -

sample = val_data_predicted[0]
sample.shape

# +
# functions:
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class Encoder(nn.Module):

  def __init__(self, seq_len, n_features, embedding_dim= 7):
    super(Encoder, self).__init__()

    self.seq_len, self.n_features = seq_len, n_features
    self.embedding_dim, self.hidden_dim = embedding_dim, 2 * embedding_dim

    # self.rnn1 = nn.LSTM(
    #   input_size=n_features,
    #   hidden_size= self.hidden_dim,
    #   num_layers=1,
    #   batch_first=True
    # )
    
    # self.rnn2 = nn.LSTM(
    #   input_size=self.hidden_dim,
    #   hidden_size=7,
    #   num_layers=1,
    #   batch_first=True
    # )

    self.lstm1 = nn.LSTM(input_size=28, hidden_size=14, num_layers=1, batch_first=True)
    self.lstm2 = nn.LSTM(input_size=14, hidden_size=7, num_layers=1, batch_first=True)

    

  def forward(self, x):
    x = x.reshape((1,self.seq_len, self.n_features))
    encoded, _ = self.lstm1(x)
    encoded, _ = self.lstm2(encoded)
    # x, (hidden_n, cell_n) = self.rnn1(x)
    # x, (hidden_n, _) = self.rnn2(hidden_n, cell_n)
    # print("num of features in encoder forward is   ", self.n_features)
    # print("hidden size of output encoder", encoded.shape) 
    # return hidden_n.reshape((1, self.embedding_dim))
    return encoded
  


class Decoder(nn.Module):

  def __init__(self, seq_len, input_dim = 7, n_features=28):
    super(Decoder, self).__init__()

    self.seq_len, self.input_dim = seq_len, input_dim
    self.hidden_dim, self.n_features = 2 * input_dim, n_features

    # self.rnn1 = nn.LSTM(
    #   input_size=input_dim,
    #   hidden_size=2*input_dim,
    #   num_layers=1,
    #   batch_first=True
    # )

    # self.rnn2 = nn.LSTM(
    #   # input_size=input_dim,
    #   input_size=2*input_dim,
    #   # hidden_size=self.hidden_dim,
    #   hidden_size= self.n_features,
    #   num_layers=1,
    #   batch_first=True
    # )

    # self.output_layer = nn.Linear(self.hidden_dim, self.n_features)


    self.lstm1 = nn.LSTM(input_size=7, hidden_size=14, num_layers=1, batch_first=True)
    self.lstm2 = nn.LSTM(input_size=14, hidden_size=28, num_layers=1, batch_first=True)


  def forward(self, x):
    # print("first forward in decoder" , x.shape)
    # x = x.repeat(self.seq_len,1)   #to fit the fixed-sized 2D output of the encoder to the differing length and 3D input expected by the decoder.
    # # print(x.shape)
    # x = x.reshape(( 1,self.seq_len, self.input_dim))
    
    # x, (hidden_n, cell_n) = self.rnn1(x)
    # x, (hidden_n, cell_n) = self.rnn2(hidden_n, cell_n)
    # # print(x.shape, "  forward decoder")
    # # x = x.reshape((self.seq_len, self.hidden_dim))
    
    # x = x.reshape((self.seq_len, self.n_features))
    # # return self.output_layer(x)
    # x = x.repeat(633,1)   #to fit the fixed-sized 2D output of the encoder to the differing length and 3D input expected by the decoder.
    # x = x.reshape(( 1,633, 7))
    decoded, _ = self.lstm1(x)
    decoded, _ = self.lstm2(decoded)

    return( decoded)
  

  

class RecurrentAutoencoder(nn.Module):

  def __init__(self, seq_len, n_features, embedding_dim=128):
    super(RecurrentAutoencoder, self).__init__()

    # print("seq_len ", seq_len, "num of features ", n_features)
    self.encoder = Encoder(seq_len, n_features, embedding_dim).to(device)
    self.decoder = Decoder(seq_len, embedding_dim, n_features).to(device)

  def forward(self, x):
    x = self.encoder(x)
    # print(x.size, "   x size")
    x = self.decoder(x)

    return x
# -





