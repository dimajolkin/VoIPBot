import os

import requests
import argparse


class YandexSpeechKit:

    def __init__(self, folder_id=None, token=None):
        self.folder_id = folder_id
        self.token = token

    def synthesize(self, text):
        url = 'https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize'
        headers = {
            'Authorization': 'Bearer ' + self.token,
        }

        data = {
            # 'text': text,
            'lang': 'ru-RU',
            'folderId': self.folder_id,
            'format': 'lpcm',
            'sampleRateHertz': 48000,
            'ssml': text,
            'voice': 'alena',
        }

        with requests.post(url, headers=headers, data=data, stream=True) as resp:
            if resp.status_code != 200:
                raise RuntimeError("Invalid response received: code: %d, message: %s" % (resp.status_code, resp.text))

            for chunk in resp.iter_content(chunk_size=None):
                yield chunk

    def convert_raw_to_wav(self, raw_file, wav_file):
        os.system("sox -r 48000 -b 16 -e signed-integer -c 1 {raw} {wav}".format(raw=raw_file, wav=wav_file))
        pass

    def write(self, file, text):
        with open(file, "wb") as f:
            for audio_content in self.synthesize(text):
                f.write(audio_content)


from dotenv import dotenv_values

if __name__ == "__main__":
    config = dotenv_values(".env")
    content = open('text/welcome.xml','r').read().replace('\n',' ')
    # yc iam create-token
    speech = YandexSpeechKit(token=config.get('YANDEX_SPEECH_KIT_AIM_TOKEN'), folder_id=config.get('YANDEX_SPEECH_KIT_FOLDER_ID'))
    speech.write('data/out.raw',content)
    speech.convert_raw_to_wav('data/out.raw', 'data/speech.wav')