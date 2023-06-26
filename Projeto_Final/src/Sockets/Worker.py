from demucs.audio import AudioFile, save_audio
from demucs.pretrained import get_model
from demucs.apply import apply_model
import logging
import argparse
import subprocess
import socket
import json
import selectors
import sys
import base64
import os
import time
import torch

torch.set_num_threads(1)

print("Worker Starting ...")


class Worker:
    def __init__(self):
        self.worker_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.worker_socket.connect(("127.0.0.1", 8001))  # connect to server
        print("Connected to server")
        self.sel = selectors.DefaultSelector()
        self.time_to_job = 0  # variable to keep track of job times
        self.sel.register(self.worker_socket, selectors.EVENT_READ, self.read)
        self.swapper = 0
        self.job_part = 1

        """
         swapper variable will be used for access control to read function
         to send files from socket server, two consecutive messages will be sent
         one with the action to be performed and file size thats gonna be sent
         and another message with the file
         only the 1st message is supposed to be processed by the read function ( because file cant be json loaded )
         so the 2nd message will be blocked with the swapper variable ( while the bytes it contains will still be read )
        """

    def read(self, conn, mask):
        if self.swapper == 0:
            message_header = int.from_bytes(conn.recv(4), "big")
            if message_header == 0:
                return

            message = json.loads(conn.recv(message_header))

            if message["action"] == "run_demucs":
                self.swapper = 1
                # time.sleep(2) # wait a bit for the 2nd message to arrive
                filesize = int(message["file_size"])
                chunk_filename = message["chunk_filename"]
                # print ("CHUNK FILENAME -> ", chunk_filename)
                part_number = int(
                    chunk_filename.split("_p")[1].split(".")[0].strip(" ")
                )
                print("PART NUMBER -> ", part_number)
                received_data = b""
                # always 10 recvs for any file size, i guess
                recv_sizes = int(filesize / 10)
                while len(received_data) < filesize:
                    chunk = conn.recv(recv_sizes)
                    if not chunk:
                        print("Error receiving data from music file data from server")
                        break
                    received_data += chunk
                # print(
                #   f"Received {len(received_data)/1024/1024:.2f} MB bytes of data")
            client_temp_dir = os.getcwd() + "/worker_storage"
            music_save_path = client_temp_dir + "/" + chunk_filename
            print(" Client temp dir is ", client_temp_dir)
            with open(music_save_path, "wb") as f:
                print(f.name)
                f.write(received_data)
                self.apply_model(f.name, chunk_filename)
                f.close()
                os.remove(music_save_path)
            print("Sucessfully wrote data to mp3 file -> worker")
            self.swapper = 0  # allow messages again

        else:
            return  # do nothing for now

    def apply_model(
        self, song, chunk_filename
    ):  # applies the model and stores the output
        # start counting time of job
        start_time = time.time()
        model = get_model(name="htdemucs")
        model.cpu()
        model.eval()
        wav = AudioFile(song).read(
            streams=0, samplerate=model.samplerate, channels=model.audio_channels
        )
        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()

        # apply the model
        sources = apply_model(
            model, wav[None], device="cpu", progress=True, num_workers=1
        )[0]
        sources = sources * ref.std() + ref.mean()

        # store the model
        music_chunk = chunk_filename.split(".mp3")[0]

        for source, name in zip(sources, model.sources):
            save_name = f"{music_chunk}_{name}.wav"
            ws2 = os.getcwd() + "/worker_storage_2"
            stem = os.path.join(ws2, save_name)
            save_audio(source, str(stem), samplerate=model.samplerate)
            self.sendback_sv(ws2, save_name, start_time)

    def sendback_sv(self, ws2, save_name, start_time):
        """
        Send back the files from worker to server

        """

        # ws2 = path para a storage 2
        # save_name = nome do ficheiro.wav
        full_path = os.path.join(ws2, save_name)
        chunk_size = os.path.getsize(full_path)
        job_time = time.time() - start_time
        message = json.dumps(
            {
                "action": "sendback",
                "file_size": str(chunk_size),
                "chunk_filename": save_name,
                "time_of_job": job_time,
                "job_part": self.job_part,
            }
        ).encode("utf-8")
        self.job_part += 1
        if self.job_part == 5:
            self.job_part = 1  # reset job
        msg_header = len(message).to_bytes(4, "big")
        with open(full_path, "rb") as f:
            new_msg = msg_header + message + f.read()
            f.close()
        with open(full_path, "wb") as f:
            f.write(new_msg)
            f.close()
        self.worker_socket.send(new_msg)
        os.remove(full_path)  # delete the files after sending them back to server

    def run(self):
        while True:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)


if __name__ == "__main__":
    worker = Worker()
    worker.run()
