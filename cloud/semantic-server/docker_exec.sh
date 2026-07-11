# reconfig nginx here for simplicity
# comment it when run in local machine instead of docker

if [ -f ".env" ]; then
    set -a
    . ./.env
    set +a
fi

if [ -f "default" ]; then
    cp default /etc/nginx/sites-enabled/default
elif [ -f "nginx_config/default" ]; then
    cp nginx_config/default /etc/nginx/sites-enabled/default
fi

service nginx restart

################

export NVI_LOG_DIR=./logs

bash cleanup.sh &
uvicorn fastapi-mask2former_detectron2:app --host 127.0.0.1 --port 8001 --root-path /mask2former &

wait
