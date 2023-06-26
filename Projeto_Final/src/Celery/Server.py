import json
import os
import math
import threading
from typing import Any, List, Dict
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
from mutagen.mp3 import MP3
import random
from glob import glob
from pydub import AudioSegment
import time


from Worker import process_music


class Server:
    def __init__(self):
        self.id_register = {}  # music_id: [ vocal_id, drums_id, bass_id, other_id]
        self.NUM_PARTS = 4  # number of parts to split the music
        self.music_path = {}  # music_id -> [music_name, music_title, music_artist]
        self.wanted_tracks = {}  # music_id -> [wanted_tracks]
        self.TIMEOUT_SCALAR = 4  # timeout scalar to multiply per second of the music
        self.received_parts = {}  # music_id -> number of parts received
        self.jobs = (
            {}
        )  # job_id ->  [job_id,music_id ,file_size, time , links for each track , track ids  ]
        self.music_stats = (
            {}
        )  # music_id -> {progress: value , instruments : [ {"name":name , "track":link} ] }, "final":link}
        self.music_size = {}  # music_id -> size of music, start time of processing

    def get_link(self, filename):
        ##print("Link request for file -> ", filename)
        # if filename not in worker_storage:
        #   print("File not found in worker storage")
        return "http://localhost:8000/" + filename

    def getprogress(self, music_id):
        first_column = []
        second_column = []
        # go to src/Celery
        current_dir = os.getcwd()
        target_dir = os.path.join(current_dir, "src", "Celery")

        with open(os.path.join(target_dir, "job_info.txt"), "r") as file:
            for line in file:
                values = line.strip().split(",")
                first_column.append(float(values[0].strip()))
                second_column.append(float(values[1].strip()))

        ratio_column = []
        for i in range(len(first_column)):
            if first_column[i] != 0:
                ratio = second_column[i] / first_column[i]
                ratio_column.append(ratio)
            else:
                ratio_column.append(0)

        average_ratio = sum(ratio_column) / len(ratio_column)

        music_size = self.music_size[int(music_id)][0]
        passed_time = time.time() - self.music_size[int(music_id)][1]
        print("Initial time:", self.music_size[int(music_id)][1])
        expected_time = average_ratio * music_size

        print("Expected time:", expected_time)
        print("Passed time:", passed_time)

        # convert passed_time / expected_time to a integer
        progress = int((passed_time / expected_time) * 100)

        progress = min(99, progress)

        return progress
        # print("Average ratio:", average_ratio)

    def mix_mp3s(self, music_id):
        server_storage = os.path.join(os.getcwd(), "server_storage")
        # print ("WANTED TRACKS" , self.wanted_tracks[music_id])
        final_music = AudioSegment.empty()
        track_list = []
        i = 0
        for track in self.wanted_tracks[music_id]:
            save_track = track  # save name of track
            if track == "vocals":
                track = self.id_register[music_id][0]
            elif track == "drums":
                track = self.id_register[music_id][1]
            elif track == "bass":
                track = self.id_register[music_id][2]
            elif track == "other":
                track = self.id_register[music_id][3]

            self.music_stats[int(music_id)]["instruments"].append(
                {"name": save_track, "track": self.get_link(f"{music_id}_{track}.wav")}
            )
            track_list.append(track)
            try:
                pattern = glob(
                    os.path.join(server_storage, f"{music_id}_p*_{track}.wav")
                )
                pattern.sort(key=lambda x: x.split("_")[1][1:])
                music = AudioSegment.empty()
                for file in pattern:
                    segment = AudioSegment.from_file(file)
                    music += segment
                music.export(
                    os.path.join(server_storage, f"{music_id}_{track}.wav"),
                    format="wav",
                )
                if i == 0:
                    final_music = music
                    i += 1
                else:
                    final_music = final_music.overlay(music)
            except Exception as e:
                print("Error mixing tracks", e)
        track_name = "+".join(map(str, track_list))
        final_music.export(
            os.path.join(server_storage, f"{music_id}_{track_name}.wav"), format="wav"
        )
        self.music_stats[int(music_id)]["final"] = self.get_link(
            f"{music_id}_{track_name}.wav"
        )
        self.music_stats[int(music_id)]["progress"] = 100

        print("Mixing complete for music", music_id)

    def split_mp3(self, mp3file, wanted_tracks):
        # audio = AudioSegment.from_mp3(mp3file)
        # server_storage = os.path.join(os.getcwd(), "server_storage")
        filename, extension = os.path.splitext(os.path.basename(mp3file))

        # mp3_file = MP3(mp3file, ID3=ID3)
        # print(mp3_file.tags)

        with open(mp3file, "rb") as f:
            filesize = os.path.getsize(mp3file)
            # Calculate the size of each chunk based on the number of workers
            chunk_size = math.ceil(filesize / self.NUM_PARTS)
            # Read and write each chunk to a separate file
            for i in range(self.NUM_PARTS):
                # Open a new file for this chunk
                # print ( "File name check", filename)
                chunk_filename = f"{filename}_p{i+1}{extension}"
                # Seek to the start of this chunk
                f.seek(i * chunk_size)
                # Read the chunk from the original file
                chunk = f.read(chunk_size)
                # print("Worker", i+1, "chunk size -> ", len(chunk))
                # create threads to take care of handoff to workers
                Thread = threading.Thread(
                    target=self.worker_handoff,
                    args=(chunk, chunk_filename, i + 1, wanted_tracks),
                )
                Thread.start()
            f.close()

    def worker_handoff(
        self, byte_chunk: bytes, chunk_filename, part_number, wanted_tracks
    ):
        ## criar informação sobre o job e guardar no self.jobs

        job_id = self.generate_id(2)
        music_id = chunk_filename.split("_")[0]
        chunk_size = len(byte_chunk)
        wanted_tracks_ids = []

        for track in wanted_tracks:
            if track == "vocals":
                wanted_tracks_ids.append(self.id_register[int(music_id)][0])
            elif track == "drums":
                wanted_tracks_ids.append(self.id_register[int(music_id)][1])
            elif track == "bass":
                wanted_tracks_ids.append(self.id_register[int(music_id)][2])
            elif track == "other":
                wanted_tracks_ids.append(self.id_register[int(music_id)][3])

        self.jobs[job_id] = [
            {"Job_id": job_id},
            {"music_id": music_id},
            {"size": str(chunk_size)},
            {"track_list": wanted_tracks_ids},
        ]
        task_data = {
            "file_size": str(chunk_size),
            "chunk_filename": chunk_filename,
            "song": byte_chunk,
            "job_id": job_id,
            "part_number": part_number,
            "wanted_tracks": wanted_tracks,
        }

        process_music.delay(task_data)  # chamar a task no worker do celery

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
