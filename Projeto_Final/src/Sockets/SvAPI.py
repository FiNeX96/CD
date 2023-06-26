from flask import Flask, jsonify, request, Response, send_from_directory
import json
from flask_cors import CORS
import os
import threading
from typing import Any, List, Dict, Tuple
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from Server import Server  # import Server object
from pydub import AudioSegment


app = Flask(__name__)
# CORS is needed to allow requests from other domains
CORS(app)


@app.route("/music", methods=["POST"])
def post_music():
    file = request.files["music_input"]
    if not file:
        return Response(
            response=json.dumps({"message": "No file was sent!"}),
            status=405,
            mimetype="application/json",
        )
    try:
        music_dir = os.path.join(os.getcwd(), "server_storage")
        music_id = server.generate_id(1)  # generate music id
        new_filename = str(music_id) + ".mp3"
        # print("Saving file:" + new_filename)
        path_to_save = os.path.join(music_dir, new_filename)
        # check if file already exists ( cant send same file twice )
        if os.path.exists(path_to_save):
            return Response(
                response=json.dumps({"message": "This song was already uploaded!"}),
                status=405,
                mimetype="application/json",
            )
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
        # save name, title and artist of song
        server.music_path[music_id] = [file.filename, audio_title, audio_artist]
        return Response(
            response=json.dumps(response, indent=4),
            status=200,
            mimetype="application/json",
        )
    except:  # catch any errors ( most likely the file is not a mp3)
        response_data = {"message": "Error uploading file!"}
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
    server.wanted_tracks[int(music_id)] = [decoded_json]  # save wanted tracks
    # print (server.wanted_tracks)
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
    # print (music_path)
    Thread = threading.Thread(
        target=server.split_mp3, args=(music_path,)
    )  # let main thread return immediatly
    Thread.start()
    return Response(
        response=json.dumps({"message": "Splitting music! \n"}),
        status=200,
        mimetype="application/json",
    )


@app.route("/<file>", methods=["GET"])
def get_file(file):
    server_storage = os.path.join(os.getcwd(), "server_storage")
    return send_from_directory(server_storage, file, as_attachment=True)


@app.route("/job", methods=["GET"])
def get_job():
    print(server.jobs.keys())
    return Response(
        response=json.dumps({"Jobs": str(list(server.jobs.keys()))}),
        status=200,
        mimetype="application/json",
    )


@app.route("/job/<job_id>", methods=["GET"])
def get_job_id(job_id):
    return Response(
        response=json.dumps({"Job": str(server.jobs[int(job_id)])}),
        status=200,
        mimetype="application/json",
    )


@app.route("/reset", methods=["POST"])
def post_reset():
    # handle POST /reset endpoint here
    return jsonify({"message": "POST /reset endpoint called"})


if __name__ == "__main__":
    server = Server()
    thread = threading.Thread(target=server.run_server)
    thread.start()
    app.run(host="0.0.0.0", port=8000)
