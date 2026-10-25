FROM node:20-bookworm
RUN apt-get update && apt-get install -y python3 python3-pip git
WORKDIR /app
COPY . .
RUN npm install
RUN pip3 install --break-system-packages -r requirements.txt
CMD ["bash", "start.sh"]