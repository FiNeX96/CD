[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-24ddc0f5d75046c5622901739e7c5dd533143b0c8e959d652212380cedb1ea36.svg)](https://classroom.github.com/a/q9wGcN9U)
# CD 2023 Project

Distributed system implementation for a karaoke app from a fictional company ( Advanced Sound Systems ), that allows users to upload a music and remove each instrument from it individually and download the resulting tracks.


The codes uses one library named [demucs](https://github.com/facebookresearch/demucs),
this library uses a deep learning model to separate the tracks.
This library requires [ffmpeg](https://ffmpeg.org/) to work.
It should be present in most Linux distributions.

## Dependencies

For Ubuntu (and other debian based linux), run the following commands:

```bash
sudo apt install ffmpeg
sudo apt install rabbitmq-server
```

## Setup

Run the following commands to setup the environement:
```bash
python3 -m venv venv
source venv/bin/activate

pip install pip --upgrade
pip install -r requirements_torch.txt
pip install -r requirements_demucs.txt
pip install -r requirements.txt
```

## Usage

To test the code, run the following commands in the project root folder:

```bash
./rabbitmq.sh or sudo rabbitmq-server ( launch RabbitMQ broker)
./run_server.sh ( launch Server/API )
./client.sh ( launch a Celery Worker )
```

Use DemoWebsite.html or CURL to test the various API endpoints and system functions.
You can use the test.json file thats in the root project folder to test the Post/Music/music_id endpoint.

## Evaluation

For evaluation purposes, the final code is in the directory src/Celery. 

The code in src/Sockets was a first implementation with sockets, that only contains part of the wanted functionalities.


## Authors

* **Mário Antunes** - [mariolpantunes](https://github.com/mariolpantunes) ( Professor )
* **Rodrigo Aguiar** - [Rodrigo Aguiar](https://github.com/FiNeX96) ( Student )
* **João Luís** - [João Luís](https://github.com/jnluis) ( Student )


## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

