docker build . --tag yodaspin
docker tag yodaspin:latest yodaspin:$(git rev-parse HEAD)