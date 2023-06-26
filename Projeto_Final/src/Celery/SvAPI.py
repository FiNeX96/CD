from flask import Flask, jsonify, request, Response, send_from_directory
import json
from flask_cors import CORS
import os
import threading
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from Server import Server  # import Server object
from pydub import AudioSegment
import random
from celery import Celery
from celery.app.control import Control
import time


app = Flask(__name__)

# CORS is needed to allow requests from other domains
CORS(app)


@app.route("/music", methods=["POST"])
def post_music():
    file = request.files["music_input"]
    # check for no file uploaded
    if not file:
        return Response(
            response=json.dumps({"message": "No file was sent!"}),
            status=405,
            mimetype="application/json",
        )
        # check if file already exists ( cant send same file twice )
    if any(file.filename in value_list for value_list in server.music_path.values()):
        for key, value in server.music_path.items():
            if file.filename in value:
                return Response(
                    response=json.dumps(
                        {
                            "message": "This song was already uploaded! \nThe id is: "
                            + str(key)
                        }
                    ),
                    status=405,
                    mimetype="application/json",
                )
    try:
        music_dir = os.path.join(os.getcwd(), "server_storage")
        music_id = server.generate_id(1)  # generate music id
        new_filename = str(music_id) + ".mp3"
        # print("Saving file:" + new_filename)
        path_to_save = os.path.join(music_dir, new_filename)
        file.save(path_to_save)  # save file to server storage
        audio_title, audio_artist = server.analyze_mp3(
            path_to_save
        )  # get audio title and artist from MP3 metadata
        vocal_id, drums_id, bass_id, other_id = [
            server.generate_id(0) for _ in range(4)
        ]  # generate track ids
        temp_list = [music_id, vocal_id, drums_id, bass_id, other_id]
        response = server.gen_response(
            temp_list, audio_title, audio_artist
        )  # generate json response
        server.id_register[music_id] = [
            vocal_id,
            drums_id,
            bass_id,
            other_id,
        ]  # save ids
        server.music_size[music_id] = [
            os.path.getsize(path_to_save) / server.NUM_PARTS
        ]  # save music size
        # save name, title and artist of song
        server.music_path[music_id] = [file.filename, audio_title, audio_artist]
        server.received_parts.setdefault(music_id, 0)
        return Response(
            response=json.dumps(response, indent=4),
            status=200,
            mimetype="application/json",
        )
    except Exception as e:  # catch any errors ( most likely the file is not a mp3)
        print("Exceção -->> ", str(e))
        response_data = {"message": "Error uploading file! Make sure the file is a mp3"}
        return Response(
            response=json.dumps(response_data), status=405, mimetype="application/json"
        )


@app.route("/music", methods=["GET"])
def get_music():
    return_msg = ""
    for i in server.id_register.keys():
        return_msg += json.dumps(
            {
                "music_id": i,
                "name": server.music_path[i][1],
                "artist": server.music_path[i][2],
                "tracks": [
                    {"name": "vocals", "track_id": server.id_register[i][0]},
                    {"name": "drums", "track_id": server.id_register[i][1]},
                    {"name": "bass", "track_id": server.id_register[i][2]},
                    {"name": "other", "track_id": server.id_register[i][3]},
                ],
            },
            indent=4,
        )
    return Response(
        response=json.dumps(return_msg), status=200, mimetype="application/json"
    )


@app.route("/music/<music_id>", methods=["POST"])
def post_music_id(music_id):
    json_file = request.files["json_input"]  # get json file
    decoded_json = json.loads(json_file.read())  # decode json file

    for i in decoded_json:  # check for invalid track ids in json file
        if i not in server.id_register[int(music_id)]:
            return Response(
                response=json.dumps(
                    {
                        "message": "Invalid track id!\nChoose a valid track id for the wanted music"
                    }
                ),
                status=404,
                mimetype="application/json",
            )

    selected = []
    for i in decoded_json:  # convert to the respective track names
        if i == server.id_register[int(music_id)][0]:
            selected.append("vocals")
        elif i == server.id_register[int(music_id)][1]:
            selected.append("drums")
        elif i == server.id_register[int(music_id)][2]:
            selected.append("bass")
        else:
            selected.append("other")

    # print(selected)
    server.wanted_tracks[int(music_id)] = selected  # save wanted tracks

    server.music_stats.setdefault(int(music_id), {})  # create music stats
    server.music_stats[int(music_id)]["progress"] = 0  # start progress
    server.music_stats[int(music_id)]["instruments"] = []
    server.music_size[int(music_id)].append(time.time())  # save start time
    music_id = str(music_id) + ".mp3"
    music_dir = os.path.join(os.getcwd(), "server_storage")
    if not os.path.exists(music_dir + "/" + music_id):
        return Response(
            response=json.dumps(
                {"message": "Music not found!\nChoose a valid music ID"}
            ),
            status=404,
            mimetype="application/json",
        )
    music_path = os.path.join(music_dir, music_id)
    Thread = threading.Thread(
        target=server.split_mp3, args=(music_path, selected)
    )  # let main thread return immediatly
    Thread.start()
    return Response(
        response=json.dumps({"message": "Splitting music! \n"}),
        status=200,
        mimetype="application/json",
    )


@app.route("/music/<music_id>", methods=["GET"])
def get_music_id(music_id):
    if int(music_id) not in server.id_register.keys():
        return Response(
            response=json.dumps(
                {"message": "Music not found!\nChoose a valid music ID"}
            ),
            status=404,
            mimetype="application/json",
        )

    if server.music_stats[int(music_id)]["progress"] != 100:
        server.music_stats[int(music_id)]["progress"] = server.getprogress(
            int(music_id)
        )

    return Response(
        response=json.dumps({"message": server.music_stats[int(music_id)]}, indent=4),
        status=200,
        mimetype="application/json",
    )


@app.route("/<file>", methods=["GET"])
def get_file(file):
    server_storage = os.path.join(os.getcwd(), "server_storage")
    return send_from_directory(server_storage, file, as_attachment=True)


@app.route("/job", methods=["GET"])
def get_job():
    return Response(
        response=json.dumps({"Jobs": str(list(server.jobs.keys()))}),
        status=200,
        mimetype="application/json",
    )


@app.route("/job/<job_id>", methods=["GET"])
def get_job_id(job_id):
    return_msg = ""

    if int(job_id) not in server.jobs.keys():
        return Response(
            response=json.dumps({"message": "Job not found!"}),
            status=404,
            mimetype="application/json",
        )
    for job in server.jobs[int(job_id)]:
        for key, value in job.items():
            return_msg += json.dumps(str(key) + " : " + str(value), indent=4)
            return_msg += "\n"
    return Response(
        response=json.dumps({"message": return_msg}),
        status=200,
        mimetype="application/json",
    )


@app.route("/reset", methods=["POST"])
def post_reset():
    app = Celery(backend="rpc://", broker="amqp://guest:guest@localhost:5672//")

    ## limpar a queue de tasks no rabbitmq
    with app.connection() as connection:
        channel = connection.channel()
        channel.queue_purge("celery")

    control = Control(app)

    active_workers = control.inspect().active().keys()

    ## cancelar as tasks do celery atuais nos workers
    for worker_name in active_workers:
        active_tasks = control.inspect().active()[worker_name]
        if active_tasks:
            task_id = active_tasks[0]["id"]
            control.revoke(task_id, destination=[worker_name], terminate=True)

    ## limpar registos
    server.id_register.clear()
    server.NUM_PARTS = 4
    server.music_path.clear()
    server.wanted_tracks.clear()
    server.TIMEOUT_SCALAR = 3
    server.received_parts.clear()
    server.jobs.clear()

    ## limpar ficheiros

    directory_path = os.path.join(os.getcwd(), "server_storage")
    file_list = os.listdir(directory_path)
    for file_name in file_list:
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
    directory_path = os.path.join(os.getcwd(), "worker_storage")

    file_list = os.listdir(directory_path)

    for file_name in file_list:
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
    directory_path = os.path.join(os.getcwd(), "worker_storage_2")
    file_list = os.listdir(directory_path)

    for file_name in file_list:
        file_path = os.path.join(directory_path, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)

    return Response(
        response=json.dumps({"message": "Server reseted!"}),
        status=200,
        mimetype="application/json",
    )


@app.route("/worker_shutdown/<job_id>", methods=["POST"])
def post_worker_shutdown(job_id):
    music_id = int(server.jobs[int(job_id)][1]["music_id"])

    server.music_size[music_id][1] = time.time()  # restart progress

    return "Worker shutdown!"


@app.route("/receive", methods=["POST"])
def post_receive():
    file = request.files["file"]
    filename = request.form.get("filename")
    job_time = request.form.get("job_time")
    music_dir = os.path.join(os.getcwd(), "server_storage")
    job_id = request.form.get("job_id")
    music_id = int(filename.split("_")[0])

    exists = any("time" in d for d in server.jobs[int(job_id)])
    if not exists:
        server.jobs[int(job_id)].append({"time": job_time.split(".")[0] + " seconds"})

    if "vocals" in filename:
        filename = filename.replace("vocals", str(server.id_register[music_id][0]))
        server.jobs[int(job_id)].append({"link_vocals": server.get_link(filename)})
    if "drums" in filename:
        filename = filename.replace("drums", str(server.id_register[music_id][1]))
        server.jobs[int(job_id)].append({"link_drums": server.get_link(filename)})
    if "bass" in filename:
        filename = filename.replace("bass", str(server.id_register[music_id][2]))
        server.jobs[int(job_id)].append({"link_bass": server.get_link(filename)})
    if "other" in filename:
        filename = filename.replace("other", str(server.id_register[music_id][3]))
        server.jobs[int(job_id)].append({"link_other": server.get_link(filename)})
    file_data = file.read()
    print("Received file  ", filename)
    with open(os.path.join(music_dir, filename), "wb") as f:
        f.write(file_data)
        f.close()

    server.received_parts[int(music_id)] += 1
    print(
        "Received total ",
        server.received_parts[int(music_id)],
        " parts of ",
        server.NUM_PARTS * len(server.wanted_tracks[music_id]),
        " for music ",
        music_id,
    )
    if server.received_parts[int(music_id)] == server.NUM_PARTS * len(
        server.wanted_tracks[music_id]
    ):
        server.mix_mp3s(music_id)
        server.received_parts.pop(int(music_id))

    return "File Received"


if __name__ == "__main__":
    server = Server()
    app.run(host="0.0.0.0", port=8000)
