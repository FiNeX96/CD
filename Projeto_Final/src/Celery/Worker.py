import requests
from demucs.audio import AudioFile, save_audio
from demucs.pretrained import get_model
from demucs.apply import apply_model
import os
import time
import torch
from celery import Celery
from celery.signals import worker_process_shutdown

torch.set_num_threads(1)

print("Worker Starting ...")

current_task_args = None


app = Celery("Worker", backend="rpc://", broker="amqp://guest:guest@localhost:5672//")
app.conf.task_acks_late = (
    True  # when a task gets canceled ( worker dies ), send it to another one
)
app.conf.worker_prefetch_multiplier = 1
app.conf.worker_shutdown = "immediate"


@app.task
def process_music(task_data):  # applies the model and stores the output
    # start counting time of job
    global current_task_args
    current_task_args = task_data
    try:
        start_time = time.time()
        task_data = dict(task_data)
        start_time = time.time()
        filesize = int(task_data["file_size"])
        song = task_data["song"]
        chunk_filename = task_data["chunk_filename"]
        job_id = task_data["job_id"]
        part_number = task_data["part_number"]
        client_temp_dir = os.getcwd() + "/../../worker_storage"
        music_save_path = client_temp_dir + "/" + chunk_filename
        wanted_tracks = list(task_data["wanted_tracks"])

        with open(music_save_path, "wb") as f:
            f.write(song)
            f.close()

        model = get_model(name="htdemucs")
        model.cpu()
        model.eval()
        wav = AudioFile(music_save_path).read(
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
        music_chunk = task_data["chunk_filename"].split(".mp3")[0]

        files_to_be_sent = []

        for source, name in zip(sources, model.sources):
            save_name = f"{music_chunk}_{name}.wav"
            ws2 = os.getcwd() + "/../../worker_storage_2"
            stem = os.path.join(ws2, save_name)
            if name in wanted_tracks:
                save_audio(source, str(stem), samplerate=model.samplerate)
                files_to_be_sent.append(save_name)

        # send back the files

        job_time = time.time() - start_time
        worker_storage = os.getcwd() + "/../../worker_storage_2"

        # open a file and and store jobsize, job time
        with open(os.path.join(os.getcwd(), "job_info.txt"), "a") as f:
            f.write(f"{filesize} , {job_time} , {job_id}  \n")

        for file in files_to_be_sent:
            print("Sending file to server", file)
            with open(os.path.join(worker_storage, file), "rb") as f:
                file_data = f.read()
                requests.post(
                    "http://localhost:8000/receive",
                    files={"file": file_data},
                    data={
                        "filename": file,
                        "job_time": job_time,
                        "job_id": job_id,
                        "part_number": part_number,
                    },
                )
                f.close()
    except Exception as e:
        print("Error occured", e)


@worker_process_shutdown.connect
def on_worker_shutdown(**kwargs):
    print("Worker shutting down")
    if current_task_args is None:
        return
    print("Sending shutdown request to server")
    job_id = current_task_args["job_id"]
    try:
        requests.post("http://localhost:8000/worker_shutdown/" + str(job_id))
    except Exception as e:
        print("API is not online, cannot send worker shutdown request")
