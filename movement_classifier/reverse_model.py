
"""collection of functions for model instances"""

# import data

from os.path import dirname, join as pjoin
import os
import sys
import time
from collections import Counter
import math

# import dlc2kinematics
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly
from sklearn.decomposition import PCA
from sklearn import preprocessing
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import rsatoolbox.data as rsd 
import rsatoolbox
from sklearn.manifold import TSNE
import seaborn as sns
import scipy.io as sio
import torch
import torch.nn as nn
from torch.nn import MaxPool1d
from torch.utils.data import Dataset
from torch.utils.data import DataLoader




class TRANS_Mov1DCNN(nn.Module):
    def __init__(self,num_classes):
        
        super(TRANS_Mov1DCNN, self).__init__()
        self.num_classes = num_classes
        self.layer1 = nn.Sequential(
            nn.ReLU(),
            nn.ConvTranspose1d(in_channels=124, out_channels=250, kernel_size=2))
        #   nn.ReLU(),
        #   nn.MaxPool1d(kernel_size=2, stride=2))

        self.layer2 = nn.Sequential(
            nn.ReLU(),
            nn.ConvTranspose1d(in_channels=250, out_channels=28, kernel_size=6))
        #   nn.ReLU(),
        #   nn.MaxPool1d(kernel_size=2, stride=2))

        self.dropout = nn.Dropout(p=0.2)
        self.relu = nn.ReLU()
        # self.atanh = torch.atanh()
        self.tanh = nn.Tanh()
        self.fc1 = nn.Linear(self.num_classes, 1000)  
        self.fc2 = nn.Linear(1000, 2000)
        # num_classes = 21
        self.fc3 = nn.Linear(2000,9672 )

    def forward(self, x):
        print("x: ", x.size())
        out = self.fc1(x)
        out = self.tanh(out)
        # out = self.tanh(out)
        out = self.dropout(out)
        print(out.size())
        out = self.fc2(out)
        out = self.tanh(out)
        # out = self.tanh(out)
        # print(out.shape)
        out = self.dropout(out)
        print(out.size())
        out = self.fc3(out)
        print(out.size())
        #deconv layers
        out = out.reshape(100,124,78)
        print(out.size())
        out = self.layer1(out)
        print(out.size())
        out = self.layer2(out)
        print(out.size())
    
        return out


class MotionDataset(Dataset):
    def __init__(self, data_dict,train=True):
        self.input_dict = data_dict
#         self.subjects = Subjects
        
        self.motions_train, self.motions_test, self.labels_train, self.labels_test = train_test_split(self.input_dict['input_model'],
                                                                        self.input_dict['labels'],test_size=0.30, random_state=42)
        

        if train:
            self.labels = self.labels_train
            self.input_array = self.motions_train
        else:
            self.labels = self.labels_test
            self.input_array = self.motions_test
            

    def __len__(self):
        return len(self.labels)
    
    def __getitem__(self, idx):
        if torch.is_tensor(idx):
            idx = idx.tolist()
        sample = (np.float32(np.squeeze(self.input_array[idx,:])), self.labels[idx])
        return sample
    
    


"""ModelHandler"""
class ModelHandler():
    def __init__(self,model,input_dict, reg ="l1" ): 
        # super(Run_model,self).__init__()
        self.model = model
        self.device = "cpu"
        self.loss_fn = nn.CrossEntropyLoss()
        self.learning_rate = 0.001
        self.optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate)
        self.reg = reg
        # Hyperparameters
        self.num_epochs = 200
        # self.num_classes = np.unique(input_dict['labels_name']).shape[0]
        self.num_classes = 20
        self.batch_size = 100
        self.input_dict = input_dict
        self.motion_train = MotionDataset(data_dict = self.input_dict,train=True )
        self.motion_test = MotionDataset(data_dict = self.input_dict,train=False)
        # Data loader
        self.train_loader = DataLoader(dataset= self.motion_train, batch_size=self.batch_size, shuffle=True)
        self.test_loader  = DataLoader(dataset=self.motion_test, batch_size=self.batch_size, shuffle=False)
        self.activation = {}
        self.le = preprocessing.LabelEncoder()
        self.le.fit(self.input_dict['labels_name'])
        # print(np.unique(input_dict['labels_name']))
        # print(np.unique(vars(self.motion_test)["labels"]))
        # self.test_labels_name = le.inverse_transform(vars(self.motion_test)["labels"])
        # self.train_labels_name =  le.inverse_transform(vars(self.motion_train)["labels"])
        

    def train(self):
        total_step = len(self.train_loader)
        loss_list = []
        acc_list = []
        for epoch in range(self.num_epochs):
            self.real_train_labels =[]
            for i, (motions, labels) in enumerate(self.train_loader):
                motions, labels = motions.to(self.device), labels.to(self.device)
                
                # print("motions",motions.shape)
                # Run the forward pass
                outputs = self.model(motions)
                self.loss = self.loss_fn(outputs, labels)

                # add regularization
                reg_lambda = 0.001
                if self.reg == "l2":
                    reg_norm = sum(p.pow(2.0).sum()for p in self.model.parameters())
                    
                if self.reg == "l1":
                    reg_norm = sum(abs(p).sum()for p in self.model.parameters())
                    
                self.loss = self.loss + reg_lambda * reg_norm
                loss_list.append(self.loss.item())

            # Backprop and perform Adam optimization
                self.optimizer.zero_grad()
                self.loss.backward()
                self.optimizer.step()

            # Track the accuracy
                total = labels.size(0)
                _, predicted = torch.max(outputs.data, 1)
                correct = (predicted == labels).sum().item()
                acc_list.append(correct / total)

                if (i + 1) % 2 == 0:
                    print(f"Epoch [{epoch+1}/{self.num_epochs}], Step [{i+1}/{total_step}], "
                        f"Loss: {self.loss.item():.4f}, "
                        f"Accuracy: {((correct / total) * 100):.2f}%")
            # print(len(self.real_train_labels))


        # plt.plot(loss_list)
        # plt.xlabel("steps")
        # plt.ylabel("loss")
        # plt.show()
        # len(loss_list)

    def test(self):
        self.model.eval()
        self.real_test_labels, self.predicted_labels = [], []
        with torch.no_grad():
            correct = 0
            total = 0
            for motions, labels in self.test_loader:
                motions, labels = motions.to(self.device), labels.to(self.device)
                self.real_test_labels += list(labels)
                outputs = self.model(motions)
                _, predicted = torch.max(outputs.data, 1)
                self.predicted_labels += list(predicted)
                total += labels.size(0)
                correct += (predicted == labels).sum().item()

        print(f"Test Accuracy of the model on the test moves: {(correct / total)*100:.3f}%")
        return((correct / total)*100)

    def layer_extractor(self,train = False):
        def get_activation(name):
            def hook(model, input, output):
                self.activation[name] = output.detach()
            return hook

        self.model.fc1.register_forward_hook(get_activation(name = 'fc1'))
        self.model.fc2.register_forward_hook(get_activation(name ='fc2'))
        self.model.fc3.register_forward_hook(get_activation(name = 'fc3'))
        if train:
            self.real_train_labels=[]
            self.traindata_loader = DataLoader(dataset= self.motion_train, batch_size=self.batch_size, shuffle=False)
            for motions, labels in self.traindata_loader:
                m, l = motions.to(self.device), labels.to(self.device)
                self.real_train_labels += list(l)
            d =vars(self.motion_train)
            labels_name = self.le.inverse_transform(self.real_train_labels)
        else:
            d =vars(self.motion_test)
            labels_name = self.le.inverse_transform(self.real_test_labels)
        x = d["input_array"]
        output = self.model(torch.Tensor(x))
        self.activation["input"] = torch.Tensor(x)
        
        return self.activation,labels_name

    def save_layerOutput(self):
        np.save("../data/03_processed/test_input.npy", self.activation["input"])
        np.save("../data/03_processed/fc1-out.npy", self.activation["fc1"])
        np.save("../data/03_processed/fc2-out.npy", self.activation["fc2"])
        np.save("../data/03_processed/fc3-out.npy", self.activation["fc3"])




    # class Plotter():
    # # def __init__(self,): 
    def plotRDM(self,plot_input = False):
        self.movements = np.unique(vars(self.motion_test)["labels"])
        conds = self.movements

        def avg_movements(data):
            for m in self.movements:
                selected_movements = np.where(self.real_test_labels == m)
            # print(selected_movements)
                Data = np.dstack(data[selected_movements,:])
                # print("dstack",Data.shape)
                if m== self.movements[0]:
                    data_all_movement = np.dstack(np.mean(Data, axis = 0))
                else:
                    B = np.dstack(np.mean(Data, axis = 0))
                    data_all_movement = np.concatenate([data_all_movement,B])

            return(data_all_movement)
        rdm = []
        #plot rdm for input layer
        if plot_input:          
            # shape = (1,20,28,554)
            d =vars(self.motion_test)
            inputdata = d["input_array"]
            # print("data shape", inputdata.shape)
            Data = avg_movements(inputdata)
            Data = Data.reshape(20,Data.shape[1]*Data.shape[2])
            obs_des = {"conds":conds}
            des = {'subj': all}
            data = rsd.Dataset(measurements=Data,
                                descriptors=des,
                                obs_descriptors=obs_des
                                )
            title = "Input for all subjects"
            rdm.append(rsatoolbox.rdm.calc_rdm(data, method="correlation", descriptor=None, noise=None))
            
            self.real_labels = [int(x) for x in self.real_test_labels]
            self.predicted_labels = [int(x) for x in self.predicted_labels]
            labels_unique = np.unique(self.real_test_labels)
            labels_name = self.le.inverse_transform(labels_unique)
            tick_names = [a.replace("_", " ") for a in labels_name]
            fig = sns.clustermap(rdm[0].get_matrices().reshape(20,20),yticklabels = tick_names,xticklabels = tick_names,vmin=0, vmax=1.5 )
            plt.setp(fig.ax_heatmap.get_xticklabels(), rotation=90) 
            plt.show()
         
        #plot rdm for layers
        else:
            
            interest_layers = ["fc1","fc2","fc3"]
            i=0
            for l in interest_layers:
                data = self.activation[l]
                # print("data shape", data.shape)
                Data = avg_movements(data.detach().numpy())
                Data = Data.reshape(20,Data.shape[1]*Data.shape[2])
                obs_des = {"conds":conds}
                des = {'subj': all}
                data = rsd.Dataset(measurements=Data,
                                    descriptors=des,
                                    obs_descriptors=obs_des
                                    )

                title = "output of {} layer".format(l)+" for all subjects"
                rdm.append( rsatoolbox.rdm.calc_rdm(data, method="correlation", descriptor=None, noise=None))
                self.real_labels = [int(x) for x in self.real_test_labels]
                self.predicted_labels = [int(x) for x in self.predicted_labels]
                labels_unique = np.unique(self.real_test_labels)
                labels_name = self.le.inverse_transform(labels_unique)
                tick_names = [a.replace("_", " ") for a in labels_name]
                fig = sns.clustermap(rdm[i].get_matrices().reshape(20,20),yticklabels = tick_names,xticklabels = tick_names,vmin=0, vmax=1.5 )
                plt.setp(fig.ax_heatmap.get_xticklabels(), rotation=90) 
                plt.show()
                i += 1
                
            # fig.savefig('../reports/figures/allsubjects_{}_rdm.png'.format(layer), bbox_inches='tight', dpi=300) 
        return(rdm)



    def plotConfusionMatrix(self):
        self.real_labels = [int(x) for x in self.real_test_labels]
        self.predicted_labels = [int(x) for x in self.predicted_labels]
        labels_unique = np.unique(self.real_test_labels)
        labels_name = self.le.inverse_transform(labels_unique)
        tick_names = [a.replace("_", " ") for a in labels_name]
        cm = confusion_matrix(self.real_labels, self.predicted_labels,labels = labels_unique,normalize='true')
        plt.figure(figsize=(8,10))
        plt.imshow(cm)
        plt.xticks(range(len(tick_names)),tick_names, rotation=90)
        plt.yticks(range(len(tick_names)),tick_names)
        plt.xlabel('predicted move')
        plt.ylabel('real move')
        plt.show()
        return(cm,tick_names)


    def plot_tsne(self,labels_name,visualization,layer,perplexity = 30, iter = 2000 ):
        u_labels = np.unique(labels_name)
        model = TSNE(n_components=2, random_state=1,learning_rate=100,perplexity=perplexity, n_iter=iter)
        if layer == "input":
            d =vars(self.motion_test)
            inputdata = d["input_array"]
            input_data = inputdata.reshape(inputdata.shape[0],inputdata.shape[1]*inputdata.shape[2])
        else:
            input_data = visualization[layer]
        tsne_data = model.fit_transform(input_data)
        cmp = ["#00FFFF", "#0000FF","#8A2BE2","#EE3B3B","#7FFF00","#EE7621","#FF1493","#FFD700","#8B2252","#FF6A6A",
        "#BFEFFF","#FFBBFF","#FFB5C5","#00CD66","#008080","#8B8B00","#CDBA96","#8B3626","#8B8989","#5E2612"]
        plt.figure(num=1, figsize=(4, 2), dpi=500, facecolor='w', edgecolor='w')
        i=0
        for ul in u_labels:
            # print(ul)
            plt.scatter(tsne_data[labels_name==ul,0], tsne_data[labels_name==ul, 1],
            label=ul,s=5,c=cmp[i],cmap=cmp)
            i+=1
        plt.axis('tight')
        plt.yticks([])
        plt.title("Input of First Layer",fontsize = 5)
        plt.xticks([])
        plt.legend(loc='upper right', bbox_to_anchor=(0, 0), ncol=1,fancybox=True, shadow=False, fontsize = 2)
        # plt.savefig('../reports/figures/input_tsne.png')
        plt.show()
        



