# -*- coding: utf-8 -*-
"""Wavegrad-partial-Demo-Mozilla-TTS-MultiSpeaker-jia-et-al-2018-With-GST-and-CorentinJ-SpeakerEncoder-and-DDC-GST-Small-with-speaker-embedding.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1Hi_ySH1hAGPELNGBipDb5i3YAEWJ-Ll7

# **Download and install Mozilla TTS**
"""

import os 
!git clone https://github.com/Edresson/TTS -b dev
#-dev-gst-embeddings

!apt-get install espeak
os.chdir('TTS')
! git pull
!pip install -r requirements.txt
!python setup.py develop
os.chdir('..')

! pip install git+https://github.com/freds0/wavegrad.git

"""

**Download Checkpoint**


"""

# config.json 
! gdown https://drive.google.com/uc?id=1YKrAQKBLVXzyYS0CQcLRW_5eGfMOIQ-2

# best checkpoint 
! gdown https://drive.google.com/uc?id=1iDCL_cRIipoig7Wvlx4dHaOrmpTQxuhT


# speakers.json 
! gdown https://drive.google.com/uc?id=1oOnPWI_ho3-UJs3LbGkec2EZ0TtEOc_6


# Download gst style example
!wget https://github.com/Edresson/TTS/releases/download/v1.0.0/gst-style-example.wav


#Download wavegrad checkpoint  

#partial model
#! gdown https://drive.google.com/uc?id=1Te-9YaUirTGOa2syq2uQwBNU1vbDlUN0

# final model:  https://drive.google.com/file/d/1LJFalcIPXIahqJbFkbMgQo-s9dq8QeLr/view?usp=sharing
! gdown https://drive.google.com/uc?id=1LJFalcIPXIahqJbFkbMgQo-s9dq8QeLr

# remove start lines
! tail -n +4 config.json > config-new.json
!rm config.json
! mv config-new.json config.json

import numpy as np
import os
import torch
import torchaudio

from argparse import ArgumentParser

from wavegrad.params import AttrDict, params as WAVEGRAD_PARAMS
from wavegrad.model import WaveGrad

import time

from tqdm import tqdm

# wavegrad 
WAVEGRAD_VOCODER_PATH = './weights.pt'

if os.path.exists(f'{WAVEGRAD_VOCODER_PATH}/weights.pt'):
  checkpoint = torch.load(f'{WAVEGRAD_VOCODER_PATH}/weights.pt')
else:
  checkpoint = torch.load(WAVEGRAD_VOCODER_PATH)


WAVEGRAD_MODEL = WaveGrad(AttrDict(WAVEGRAD_PARAMS))
WAVEGRAD_MODEL.load_state_dict(checkpoint['model'])
WAVEGRAD_MODEL.eval()
print("WaveGrad load !")
# get this with noise_schedule search


WAVEGRAD_PARAMS['noise_schedule'] = [4.47739327e-06, 4.47739327e-05, 9.49513587e-04, 9.49513587e-03, 9.49513587e-02, 4.47739327e-01]

# partial model 
# 6 iter: [4.47739327e-06, 4.47739327e-05, 9.49513587e-04, 9.49513587e-03, 9.49513587e-02, 4.47739327e-01] 

# final model: 
# 4 iter: [2.4370316798529143e-06, 0.00020868883938539648, 0.0036565719045585756, 0.47684367922668963]
# 6 iter:  [3.88983768e-07, 6.47229878e-05, 5.55715506e-04, 7.88519477e-03, 3.88983768e-03, 8.05331347e-01]


def wavegrad_predict(spectrogram, device=torch.device('cuda')):
  start = time.time()
  # Lazy load model.
  model = WAVEGRAD_MODEL.to(device)
  model.params.override(WAVEGRAD_PARAMS)
  with torch.no_grad():
    beta = np.array(model.params.noise_schedule)
    alpha = 1 - beta
    alpha_cum = np.cumprod(alpha)

    # Expand rank 2 tensors by adding a batch dimension.
    if len(spectrogram.shape) == 2:
      spectrogram = spectrogram.unsqueeze(0)
    spectrogram = spectrogram.to(device)

    audio = torch.randn(spectrogram.shape[0], model.params.hop_length * spectrogram.shape[-1], device=device)
    noise_scale = torch.from_numpy(alpha_cum**0.5).float().unsqueeze(1).to(device)

    for n in tqdm(range(len(alpha) - 1, -1, -1)):
      c1 = 1 / alpha[n]**0.5
      c2 = (1 - alpha[n]) / (1 - alpha_cum[n])**0.5
      audio = c1 * (audio - c2 * model(audio, spectrogram, noise_scale[n]).squeeze(1))
      if n > 0:
        noise = torch.randn_like(audio)
        sigma = ((1.0 - alpha_cum[n-1]) / (1.0 - alpha_cum[n]) * beta[n])**0.5
        audio += sigma * noise
      audio = torch.clamp(audio, -1.0, 1.0)
  print('Wavegrad Time', time.time()-start)
  return audio.cpu().numpy(), model.params.sample_rate

"""**Utils Functions**"""

# Commented out IPython magic to ensure Python compatibility.
# %load_ext autoreload
# %autoreload 2
import argparse
import json
# pylint: disable=redefined-outer-name, unused-argument
import os
import string
import time
import sys
import numpy as np

TTS_PATH = "../content/TTS"
# add libraries into environment
sys.path.append(TTS_PATH) # set this if TTS is not installed globally

import torch

from TTS.tts.utils.generic_utils import setup_model
from TTS.tts.utils.synthesis import synthesis
from TTS.tts.utils.text.symbols import make_symbols, phonemes, symbols
from TTS.utils.audio import AudioProcessor
from TTS.utils.io import load_config
from TTS.vocoder.utils.generic_utils import setup_generator

from wavegrad.params import params

count = 0
def tts(model, vocoder_model, text, CONFIG, use_cuda, ap, use_gl, speaker_fileid, speaker_embedding=None, gst_style=None):
    global count
    t_1 = time.time()
    waveform, _, _, mel_postnet_spec, _, _ = synthesis(model, text, CONFIG, use_cuda, ap, speaker_fileid, gst_style, False, CONFIG.enable_eos_bos_chars, use_gl, speaker_embedding=speaker_embedding)
    if CONFIG.model == "Tacotron" and not use_gl:
        mel_postnet_spec = ap.out_linear_to_mel(mel_postnet_spec.T).T
    if not use_gl:
        waveform = vocoder_model.inference(torch.FloatTensor(mel_postnet_spec.T).unsqueeze(0))
    if use_cuda and not use_gl:
        waveform = waveform.cpu()
    if not use_gl:
        waveform = waveform.numpy()
    waveform = waveform.squeeze()
    torch.save(mel_postnet_spec.T, str(count)+'_spec.pt')
    waveform_wavegrad, _ = wavegrad_predict(torch.FloatTensor(mel_postnet_spec.T))

    '''spec = torch.load('0_spec.pt')
    wav, sr = wavegrad_predict(torch.FloatTensor(spec), WAVEGRAD_VOCODER_PATH, params=params)
    IPython.display.display(Audio(wav, rate=sr))'''

    count+= 1
    rtf = (time.time() - t_1) / (len(waveform) / ap.sample_rate)
    tps = (time.time() - t_1) / len(waveform)
    print(" > Run-time: {}".format(time.time() - t_1))
    print(" > Real-time factor: {}".format(rtf))
    print(" > Time per step: {}".format(tps))
    return waveform, waveform_wavegrad



"""# **Vars definitions**

"""

TEXT = ''
OUT_PATH = 'tests-audios/'
# create output path
os.makedirs(OUT_PATH, exist_ok=True)

SPEAKER_FILEID = None # if None use the first embedding from speakers.json

# model vars 
MODEL_PATH = 'best_model.pth.tar'
CONFIG_PATH = 'config.json'
SPEAKER_JSON = 'speakers.json'

# vocoder vars
VOCODER_PATH = ''
VOCODER_CONFIG_PATH = ''


USE_CUDA = True

"""# **Restore  TTS Model**"""

# load the config
C = load_config(CONFIG_PATH)
C.forward_attn_mask = True

# load the audio processor
ap = AudioProcessor(**C.audio)

# if the vocabulary was passed, replace the default
if 'characters' in C.keys():
    symbols, phonemes = make_symbols(**C.characters)

speaker_embedding = None
speaker_embedding_dim = None
num_speakers = 0
# load speakers
if SPEAKER_JSON != '':
    speaker_mapping = json.load(open(SPEAKER_JSON, 'r'))
    num_speakers = len(speaker_mapping)
    if C.use_external_speaker_embedding_file:
        if SPEAKER_FILEID is not None:
            speaker_embedding = speaker_mapping[SPEAKER_FILEID]['embedding']
        else: # if speaker_fileid is not specificated use the first sample in speakers.json
            choise_speaker = list(speaker_mapping.keys())[0]
            print(" Speaker: ",choise_speaker.split('_')[0],'was chosen automatically')
            speaker_embedding = speaker_mapping[choise_speaker]['embedding']
        speaker_embedding_dim = len(speaker_embedding)

# load the model
num_chars = len(phonemes) if C.use_phonemes else len(symbols)
model = setup_model(num_chars, num_speakers, C, speaker_embedding_dim)
cp = torch.load(MODEL_PATH, map_location=torch.device('cpu'))
model.load_state_dict(cp['model'])
model.eval()

if USE_CUDA:
    model.cuda()

model.decoder.set_r(cp['r'])

# load vocoder model
if VOCODER_PATH!= "":
    VC = load_config(VOCODER_CONFIG_PATH)
    vocoder_model = setup_generator(VC)
    vocoder_model.load_state_dict(torch.load(VOCODER_PATH, map_location="cpu")["model"])
    vocoder_model.remove_weight_norm()
    if USE_CUDA:
        vocoder_model.cuda()
    vocoder_model.eval()
else:
    vocoder_model = None
    VC = None

# synthesize voice
use_griffin_lim = VOCODER_PATH== ""

if not C.use_external_speaker_embedding_file:
    if SPEAKER_FILEID.isdigit():
        SPEAKER_FILEID = int(SPEAKER_FILEID)
    else:
        SPEAKER_FILEID = None
else:
    SPEAKER_FILEID = None

"""Synthesize sentence with Speaker

> Use "q" to leave!


"""

import IPython
from IPython.display import Audio
print("Synthesize sentence with Speaker: ",choise_speaker.split('_')[0], "(this speaker seen in training)")
gst_style = {"0": 0, "1": 0, "3": 0, "4": 0}
while True:
  TEXT = input("Enter sentence: ")
  if TEXT == 'q':
    break
  print(" > Text: {}".format(TEXT))
  wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
  print("GL")
  IPython.display.display(Audio(wav, rate=ap.sample_rate))
  print("WAVEGRAD")
  IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
  # save the results
  file_name = TEXT.replace(" ", "_")
  file_name = file_name.translate(
      str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
  out_path = os.path.join(OUT_PATH, file_name)
  print(" > Saving output to {}".format(out_path))
  ap.save_wav(wav, out_path)

"""# **Select Speaker**


"""

# VCTK speakers not seen in training (new speakers)
VCTK_test_Speakers = ["p225", "p234", "p238", "p245", "p248", "p261", "p294", "p302", "p326", "p335", "p347"] 

# VCTK speakers seen in training
train_Speakers = ['p244', 'p300', 'p303', 'p273', 'p292', 'p252', 'p254', 'p269', 'p345', 'p274', 'p363', 'p285', 'p351', 'p361', 'p295', 'p266', 'p307', 'p230', 'p339', 'p253', 'p310', 'p241', 'p256', 'p323', 'p237', 'p229', 'p298', 'p336', 'p276', 'p305', 'p255', 'p278', 'p299', 'p265', 'p267', 'p280', 'p260', 'p272', 'p262', 'p334', 'p283', 'p247', 'p246', 'p374', 'p297', 'p249', 'p250', 'p304', 'p240', 'p236', 'p312', 'p286', 'p263', 'p258', 'p313', 'p376', 'p279', 'p340', 'p362', 'p284', 'p231', 'p308', 'p277', 'p275', 'p333', 'p314', 'p330', 'p264', 'p226', 'p288', 'p343', 'p239', 'p232', 'p268', 'p270', 'p329', 'p227', 'p271', 'p228', 'p311', 'p301', 'p293', 'p364', 'p251', 'p317', 'p360', 'p281', 'p243', 'p287', 'p233', 'p259', 'p316', 'p257', 'p282', 'p306', 'p341', 'p318']
num_samples_speaker = 2 # In theory the more samples of the speaker the more similar to the real voice it will be!

"""## **Example select  a VCTK seen speaker in training**"""

# get embedding
Speaker_choise = train_Speakers[0] # choise one of training speakers
# load speakers
if SPEAKER_JSON != '':
    speaker_mapping = json.load(open(SPEAKER_JSON, 'r'))
    if C.use_external_speaker_embedding_file:
        speaker_embeddings = []
        for key in list(speaker_mapping.keys()):
          #print(Speaker_choise,speaker_mapping[key]['name'])
          if Speaker_choise in speaker_mapping[key]['name']:
            if len(speaker_embeddings) < num_samples_speaker:
              speaker_embeddings.append(speaker_mapping[key]['embedding'])
        # takes the average of the embedings samples of the announcers
        speaker_embedding = np.mean(np.array(speaker_embeddings), axis=0).tolist()

import IPython
from IPython.display import Audio
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker seen in training)")
while True:
  TEXT = input("Enter sentence: ")
  if TEXT == 'q':
    break
  print(" > Text: {}".format(TEXT))
  wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
  print("GL")
  IPython.display.display(Audio(wav, rate=ap.sample_rate))
  print("WAVEGRAD")
  IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
  # save the results
  file_name = TEXT.replace(" ", "_")
  file_name = file_name.translate(
      str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
  out_path = os.path.join(OUT_PATH, file_name)
  print(" > Saving output to {}".format(out_path))
  ap.save_wav(wav, out_path)

"""## **Example select  a VCTK not seen speaker in training (new Speakers)**


> Fitting new Speakers :)


"""

# get embedding
Speaker_choise = VCTK_test_Speakers[2] # choise one of training speakers
# load speakers
if SPEAKER_JSON != '':
    speaker_mapping = json.load(open(SPEAKER_JSON, 'r'))
    if C.use_external_speaker_embedding_file:
        speaker_embeddings = []
        for key in list(speaker_mapping.keys()):
          if Speaker_choise in speaker_mapping[key]['name']:
            if len(speaker_embeddings) < num_samples_speaker:
              speaker_embeddings.append(speaker_mapping[key]['embedding'])
        # takes the average of the embedings samples of the announcers
        speaker_embedding = np.mean(np.array(speaker_embeddings), axis=0).tolist()

import IPython
from IPython.display import Audio
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0])
gst_style = {"0": 0, "1": 0, "3": 0, "4": 0}#'gst-style-example.wav'#
while True:
  TEXT = input("Enter sentence: ")
  if TEXT == 'q':
    break
  print(" > Text: {}".format(TEXT))
  wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
  print("GL")
  IPython.display.display(Audio(wav, rate=ap.sample_rate))
  print("WAVEGRAD")
  IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
  # save the results
  file_name = TEXT.replace(" ", "_")
  file_name = file_name.translate(
      str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
  out_path = os.path.join(OUT_PATH, file_name)
  print(" > Saving output to {}".format(out_path))
  ap.save_wav(wav, out_path)

"""# **Changing GST tokens manually (without wav reference)**

You can define tokens manually, this way you can increase/decrease the function of a given GST token. For example a token is responsible for the length of the speaker's pauses, if you increase the value of that token you will have longer pauses and if you decrease it you will have shorter pauses.
"""

# set gst tokens, in this model we have 5 tokens
gst_style = {"0": 0, "1": 0, "3": 0, "4": 0}

import IPython
from IPython.display import Audio
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker  not seen in training (new speaker))")
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

gst_style = {"0": 0.4, "1": 0, "3": 0, "4": 0}
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker  not seen in training (new speaker))")
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

gst_style = {"0": -0.1, "1": 0, "3": 0, "4": 0}
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker  not seen in training (new speaker))")
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

gst_style = {"0": 0, "1": 0.5, "3": 0, "4": 0}
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker  not seen in training (new speaker))")
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

gst_style = {"0": 0, "1": -0.5, "3": 0, "4": 0}
print("Synthesize sentence with Speaker: ",Speaker_choise.split('_')[0], "(this speaker  not seen in training (new speaker))")
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

"""# **Example Synthesizing with your own voice :)**

Download and load GE2E Speaker Encoder
"""

# Clone encoder 
!git clone https://github.com/Edresson/GE2E-Speaker-Encoder.git
#os.chdir('Real-Time-Voice-Cloning/')

#Install voxceleb_trainer Requeriments
!python -m pip install umap-learn visdom webrtcvad librosa>=0.5.1 matplotlib>=2.0.2 numpy




#Download encoder Checkpoint
!wget https://github.com/Edresson/Real-Time-Voice-Cloning/releases/download/checkpoints/pretrained.zip
!unzip pretrained.zip




import sys
# add libraries into environment
sys.path.append("../content/GE2E-Speaker-Encoder/") # set this if TTS is not installed globally
from encoder import inference as encoder
from encoder.params_model import model_embedding_size as speaker_embedding_size
from pathlib import Path



print("Preparing the encoder, the synthesizer and the vocoder...")
encoder.load_model(Path('encoder/saved_models/pretrained.pt'))
print("Testing your configuration with small inputs.")
# Forward an audio waveform of zeroes that lasts 1 second. Notice how we can get the encoder's
# sampling rate, which may differ.
# If you're unfamiliar with digital audio, know that it is encoded as an array of floats 
# (or sometimes integers, but mostly floats in this projects) ranging from -1 to 1.
# The sampling rate is the number of values (samples) recorded per second, it is set to
# 16000 for the encoder. Creating an array of length <sampling_rate> will always correspond 
# to an audio of 1 second.
print("\tTesting the encoder...")

wav = np.zeros(encoder.sampling_rate)    
embed = encoder.embed_utterance(wav)
print(embed.shape)

# Embeddings are L2-normalized (this isn't important here, but if you want to make your own 
# embeddings it will be).
#embed /= np.linalg.norm(embed) # for random embedding

# select one or more wav files
from google.colab import files
file_list = files.upload()

# extract embedding from wav files
speaker_embeddings = []
for name in file_list.keys():
    if '.wav' in name:
      preprocessed_wav = encoder.preprocess_wav(name)
      embedd = encoder.embed_utterance(preprocessed_wav)
      #embedd = se_model.compute_embedding(mel_spec).cpu().detach().numpy().reshape(-1)
      speaker_embeddings.append(embedd)
    else:
      print("You need upload Wav files, others files is not supported !!")

# takes the average of the embedings samples of the announcers
speaker_embedding = np.mean(np.array(speaker_embeddings), axis=0).tolist()

import IPython
from IPython.display import Audio
print("Synthesize sentence with New Speaker using files: ",file_list.keys(), "(this speaker not seen in training (new speaker))")
gst_style = {"0": 0.0, "1": 0.0, "3": 0.0, "4": 0.0}
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

"""Uploading your own GST reference wav file"""

# select one wav file for GST reference
from google.colab import files
file_list = files.upload()

print("Synthesize sentence with New Speaker using files: ",file_list.keys(), "(this speaker not seen in training (new speaker))")
gst_style = list(file_list.keys())[0]
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)

"""# **Example Synthesizing with Artificial Voice :)**

This can be used to generate new speakers, for example to train an automatic speech recognizer !
"""

import IPython
from IPython.display import Audio
import numpy as np
TEXT = input("Enter sentence: ")
for i in range(10):
  # Generate a random embedding
  speaker_embedding = np.random.normal(size=256)
  # apply L2 norm in embedding
  speaker_embedding /= np.linalg.norm(speaker_embedding)

  print("Synthesize sentence with New Speaker using a Artificial Speaker")
  gst_style = {"0": 0, "1": 0.0, "3": 0, "4": 0} #'gst-style-example.wav'#

  print(" > Text: {}".format(TEXT))
  wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
  print("GL")
  IPython.display.display(Audio(wav, rate=ap.sample_rate))
  print("WAVEGRAD")
  IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
  # save the results
  file_name = TEXT.replace(" ", "_")
  file_name = file_name.translate(
      str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
  out_path = os.path.join(OUT_PATH, file_name)
  print(" > Saving output to {}".format(out_path))
  ap.save_wav(wav, out_path)

# with gst reference
import IPython
from IPython.display import Audio
import numpy as np
TEXT = input("Enter sentence: ")
for i in range(10):
  # Generate a random embedding
  speaker_embedding = np.random.normal(size=256)
  # apply L2 norm in embedding
  speaker_embedding /= np.linalg.norm(speaker_embedding)

  print("Synthesize sentence with New Speaker using a Artificial Speaker")
  gst_style = 'gst-style-example.wav'#

  print(" > Text: {}".format(TEXT))
  wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
  print("GL")
  IPython.display.display(Audio(wav, rate=ap.sample_rate))
  print("WAVEGRAD")
  IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
  # save the results
  file_name = TEXT.replace(" ", "_")
  file_name = file_name.translate(
      str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
  out_path = os.path.join(OUT_PATH, file_name)
  print(" > Saving output to {}".format(out_path))
  ap.save_wav(wav, out_path)

"""Generate a random gst style. This can also be useful for training speech recognition models as it brings a greater variety to the speech of the synthesizer."""

# definitions
gst_max_factor = 0.1 # its used for get random. In my test its saife and the TTS model work fine in this interval

gst_style = {"0": np.random.uniform(-gst_max_factor, gst_max_factor), "1": np.random.uniform(-gst_max_factor, gst_max_factor), "3": np.random.uniform(-gst_max_factor, gst_max_factor), "4": np.random.uniform(-gst_max_factor, gst_max_factor)}
TEXT = input("Enter sentence: ")
print(" > Text: {}".format(TEXT))
wav, wav_wavegrad = tts(model, vocoder_model, TEXT, C, USE_CUDA, ap, use_griffin_lim, SPEAKER_FILEID, speaker_embedding=speaker_embedding, gst_style=gst_style)
print("GL")
IPython.display.display(Audio(wav, rate=ap.sample_rate))
print("WAVEGRAD")
IPython.display.display(Audio(wav_wavegrad, rate=ap.sample_rate))
# save the results
file_name = TEXT.replace(" ", "_")
file_name = file_name.translate(
    str.maketrans('', '', string.punctuation.replace('_', ''))) + '.wav'
out_path = os.path.join(OUT_PATH, file_name)
print(" > Saving output to {}".format(out_path))
ap.save_wav(wav, out_path)