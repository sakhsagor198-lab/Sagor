FROM node:20-bullseye
RUN apt-get update && apt-get install -y python3 python3-pip git
WORKDIR /app
COPY . .
RUN npm install
RUN pip3 install -r requirements.txt
CMD ["bash", "start.sh"]
