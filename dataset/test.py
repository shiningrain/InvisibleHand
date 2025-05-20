import pickle

file_path = './dataset.pkl'

with open(file_path, 'rb') as f:
    data = pickle.load(f)
