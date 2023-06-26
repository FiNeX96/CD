import socket
import selectors
import json
import os
import math
import threading
import io
from typing import Any, List, Dict, Tuple
from mutagen.easyid3 import EasyID3
import random
from glob import glob
from pydub import AudioSegment
import time


class Server:
    def __init__(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("127.0.0.1", 8001))
        self.server_socket.listen(20)
        self.worker_id = 1  # worker id counter
        host, port = self.server_socket.getsockname()
        self.workers = {}  # worker_id -> worker_socket
        print(f"Socket initialized with host {host} and port {port}")
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.server_socket, selectors.EVENT_READ, self.accept)
        # music_id: [ vocal_id, drums_id, bass_id, other_id]
        self.id_register = {}
        # music_id -> [music_name, music_title, music_artist]
        self.music_path = {}
        self.wanted_tracks = {}  # music_id -> [wanted_tracks]
        self.TIMEOUT_SCALAR = 3  # timeout scalar to multiply per second of the music
        # job_id ->  [music_id ,file_size, time , (link1,id1) , (link2,id2) , (link3,id3) , (link 4,id4) ]
        self.jobs = {}
        self.keepout = 0

    def accept(self, sock, mask):
        conn, addr = sock.accept()
        self.workers[self.worker_id] = conn
        print("New worker: ", self.worker_id, " connected", " with address: ", addr)
        self.worker_id += 1
        self.sel.register(conn, selectors.EVENT_READ, self.read)

    def read(self, conn, mask):
        header = int.from_bytes(conn.recv(4), "big")
        if header == 0:
            return
        msg = json.loads(conn.recv(header))
        """ save music info sent by workers"""
        if msg["action"] == "sendback":
            file_size = int(msg["file_size"])
            ws = os.getcwd() + "/server_storage"
            job_time = int(msg["time_of_job"])
            job_part = int(msg["job_part"])
            # print("Job time -> ", job_time , " job part -> ", job_part)
            chunk_filename = msg["chunk_filename"]
            music_id = int(chunk_filename.split("_")[0])
            if job_part == 4:
                job_id = self.generate_id(2)
                # create job info
                vocal_id = self.id_register[music_id][0]
                drums_id = self.id_register[music_id][1]
                bass_id = self.id_register[music_id][2]
                other_id = self.id_register[music_id][3]
                self.jobs[job_id] = [
                    music_id,
                    file_size,
                    job_time,
                    (self.get_link(f"{music_id}_{vocal_id}.wav"), vocal_id),
                    (self.get_link(f"{music_id}_{drums_id}.wav"), drums_id),
                    (self.get_link(f"{music_id}_{bass_id}.wav"), bass_id),
                    (self.get_link(f"{music_id}_{other_id}.wav"), other_id),
                ]
                print("Job info -> ", self.jobs[job_id])
            if "vocals" in chunk_filename:
                chunk_filename = chunk_filename.replace(
                    "vocals", str(self.id_register[music_id][0])
                )
            if "drums" in chunk_filename:
                chunk_filename = chunk_filename.replace(
                    "drums", str(self.id_register[music_id][1])
                )
            if "bass" in chunk_filename:
                chunk_filename = chunk_filename.replace(
                    "bass", str(self.id_register[music_id][2])
                )
            if "other" in chunk_filename:
                chunk_filename = chunk_filename.replace(
                    "other", str(self.id_register[music_id][3])
                )
            full_path = os.path.join(ws, chunk_filename)
            with open(full_path, "wb") as f:
                # print(f.name)
                received_data = b""
                recv_sizes = int(file_size / 10)
                while len(received_data) < file_size:
                    chunk = conn.recv(recv_sizes)
                    if not chunk:
                        print("Error receiving data from music file data from worker")
                        break
                    received_data += chunk
                f.write(received_data)
                f.close()
            self.keepout += 1
            worker_amount = len(self.workers.keys())
            if self.keepout == worker_amount * 4:
                self.mix_mp3s(music_id)
                self.keepout = 0
        # else:
        # desconectar cliente etcs

    def get_link(self, filename):
        print("Link request for file -> ", filename)
        # if filename not in worker_storage:
        #   print("File not found in worker storage")
        return "http://localhost:8000/" + filename

    def mix_mp3s(self, music_id):
        server_storage = os.path.join(os.getcwd(), "server_storage")
        for track in self.id_register[music_id]:
            pattern = glob(os.path.join(server_storage, f"{music_id}_p*_{track}.wav"))
            pattern.sort(key=lambda x: x.split("_")[1][1:])
            music = AudioSegment.empty()
            for file in pattern:
                segment = AudioSegment.from_wav(file)
                music += segment
            music.export(
                os.path.join(server_storage, f"{music_id}_{track}.wav"), format="wav"
            )
        print("Mixing complete")

    def split_mp3(self, mp3file):
        num_workers = len(self.workers.keys())
        print("number of workers -> ", num_workers)
        if num_workers == 0:
            print("No workers connected !!!!!")
            return
        with open(mp3file, "rb") as f:
            filesize = os.path.getsize(mp3file)
            # Calculate the size of each chunk based on the number of workers
            chunk_size = math.ceil(filesize / num_workers)
            # Read and write each chunk to a separate file
            for i in range(num_workers):
                # Open a new file for this chunk
                filename, extension = os.path.splitext(mp3file)
                # print ( "File name check", filename)
                chunk_filename = f"{os.path.basename(filename)}_p{i+1}{extension}"
                # Seek to the start of this chunk
                f.seek(i * chunk_size)
                # Read the chunk from the original file
                chunk = f.read(chunk_size)
                # print("Worker", i+1, "chunk size -> ", len(chunk))
                # create threads to take care of handoff to workers
                Thread = threading.Thread(
                    target=self.worker_handoff, args=(chunk, chunk_filename, i + 1)
                )
                Thread.start()

            f.close()
            # remove the original file and dir from storage
        print("Removing original file from storage ")
        os.remove(filename + extension)

    def worker_handoff(self, byte_chunk: bytes, chunk_filename, worker_num):
        worker = self.workers[worker_num]
        chunk_size = len(byte_chunk)  # get the number of bytes in byte chunk
        message = json.dumps(
            {
                "action": "run_demucs",
                "file_size": str(chunk_size),
                "chunk_filename": chunk_filename,
            }
        )
        # send file preceding message to worker
        worker.sendall(len(message).to_bytes(4, "big") + message.encode("utf-8"))
        print("Sent file preceding message to worker", worker_num)
        with io.BytesIO(byte_chunk) as f:
            _ = worker.sendfile(f)  # send the file
        print("Sent file to worker", worker_num)
        return

    def analyze_mp3(self, mp3file):
        audio_tags = EasyID3(mp3file)
        audio_title = audio_tags.get("title")
        audio_artist = audio_tags.get("artist")
        return audio_title, audio_artist

    def generate_id(self, marker) -> int:
        """
        generate random int with size 3
        marker signifies whether it is a music id or identifier id or job id
        marker = 0 -> music id
        marker = 1 -> identifier id
        marker = 2 -> job id
        im assuming we can have similar ids as long as one is for a music, one is for a identifier
        """
        possible_id = random.randint(100, 999)

        temp_list = [item for sublist in self.id_register.values() for item in sublist]

        temp_list_2 = self.jobs.values()
        # convert the various lists given by .values() to a single one

        # if it's already in the list, generate another one
        if possible_id in temp_list and marker == 1:  # no repeated identifier ids
            self.generate_id(marker)

        if possible_id in temp_list and marker == 0:  # no repeated music ids
            self.generate_id(marker)

        if possible_id in temp_list_2 and marker == 2:  # no repeated job ids
            self.generate_id(marker)

        return possible_id

    def gen_response(self, id_list, audio_title, audio_artist):
        return json.dumps(
            {
                "music_id": id_list[0],
                "name": audio_title,
                "artist": audio_artist,
                "tracks": [
                    {"name": "vocals", "track_id": id_list[1]},
                    {"name": "drums", "track_id": id_list[2]},
                    {"name": "bass", "track_id": id_list[3]},
                    {"name": "other", "track_id": id_list[4]},
                ],
            },
            indent=4,
        )

    def run_server(self):
        while True:
            events = self.sel.select()
            for key, mask in events:
                callback = key.data
                callback(key.fileobj, mask)
        exit()
