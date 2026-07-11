import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(CURRENT_DIR)


import pyaudio
import numpy as np
import dashscope
from dashscope.audio.asr import (Recognition, RecognitionCallback, RecognitionResult)


from speech_model import ModelSpeech
from model_zoo.speech_model.keras_backend import SpeechModel251BN
from speech_features import Spectrogram
from language_model3 import ModelLanguage
from utils.tools import suppress_stdout_stderr


class ASRTSpeech():
    def __init__(self,duration=5) -> None:
        # init param
        self.duration=duration
        self.channels=1
        self.sampling_rate=16000
        self.sampling_bits=16
        self.chunk_size=1024

        # init tools
        self.stream = None
        self.audio = None

        # load model
        # os.environ["CUDA_VISIBLE_DEVICES"] = "0"
        AUDIO_LENGTH = 1600
        AUDIO_FEATURE_LENGTH = 200
        CHANNELS = 1
        OUTPUT_SIZE = 1428
        # sm251bn = SpeechModel251BN(
        #     input_shape=(AUDIO_LENGTH, AUDIO_FEATURE_LENGTH, CHANNELS),
        #     output_size=OUTPUT_SIZE
        # )
        # feat = Spectrogram()
        # self.ms = ModelSpeech(sm251bn, feat, max_label_length=64)
        # cureent_dir = os.path.dirname(os.path.abspath(__file__))
        # self.ms.load_model(cureent_dir+'/save_models/' + sm251bn.get_model_name() + '.model.h5')
        # self.ml = ModelLanguage(cureent_dir+'/model_language')
        # self.ml.load_model()

        

    def recognize_speech(self,wave_data):
        with suppress_stdout_stderr():
            res = self.ms.recognize_speech(wave_data,self.sampling_rate)
        str_pinyin = res
        res = self.ml.pinyin_to_text(str_pinyin)
        return res,str_pinyin

    def open_audio(self):

        format_ = None
        if self.sampling_bits == 8:
            format_ = pyaudio.paInt8
        if self.sampling_bits == 16:
            format_ = pyaudio.paInt16
        elif self.sampling_bits == 24:
            format_ = pyaudio.paInt24
        elif self.sampling_bits == 32:
            format_ = pyaudio.paFloat32
        else:
            raise ValueError('Unsupported sampling bits')

        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(format=format_,
                            channels=self.channels,
                            rate=self.sampling_rate,
                            input=True,
                            frames_per_buffer=self.chunk_size)
        print('Audio is opened.')
    
    def close_audio(self):
        if self.stream is None or self.audio is None:
            return
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()
        self.stream = None
        self.audio = None

    def read_wave(self):
        if self.stream is None:
            raise NameError('Audio stream is not opened.')
        frames = []
        for _ in range(0, int(self.sampling_rate / self.chunk_size * self.duration)):
            data = self.stream.read(self.chunk_size)
            frames.append(data)
        wave_data = b''.join(frames)
        wave_data = np.frombuffer(wave_data, dtype = np.short) 
        wave_data.shape = -1, 1 
        wave_data = wave_data.T
        return wave_data 
    
    def __del__(self):
        self.close_audio()

class Callback(RecognitionCallback):
    def __init__(self) -> None:
        super().__init__()
        self.mic = None
        self.stream = None
        self.counter = 0
        self.msg_list = []

    def on_open(self) -> None:
        self.mic = pyaudio.PyAudio()
        self.stream = self.mic.open(
            format = pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True
        )
    
    def on_close(self) -> None:
        print('RecognitionCallback close.')
        self.stream.stop_stream()

    def on_event(self, result: RecognitionResult) -> None:
        if result.get_sentence()['end_time'] is not None:
            text = result.get_sentence()['text']
            print(text)
            self.msg_list.append(text)
            self.counter += 1


# if __name__ == '__main__':
    # asrt_speech  = ASRTSpeech()
    # asrt_speech.open_audio()
    # ress = []
    # for i in range(2):
    #     wave_data = asrt_speech.read_wave()
    #     res  = asrt_speech.recognize_speech(wave_data)
    #     ress.append(res)
    #     print(i,'语音识别最终结果：\n', res)

    # asrt_speech.close_audio()