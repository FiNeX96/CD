sudo rabbitmq-server
sudo rabbitmqctl set_permissions -p / guest ".*" ".*" ".*" # need to be able to access the queues to purge them on reset
# sudo rabbitmq-plugins enable rabbitmq_management
# site das estatisticas -> http://localhost:15672/
