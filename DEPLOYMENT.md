# Деплой на Ubuntu Server

## Локальная машина

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_GITHUB_REPO_URL
git push -u origin main
```

## Сервер Ubuntu

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg git
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
cd ~
git clone YOUR_GITHUB_REPO_URL tts_projects
cd tts_projects
python3 -m venv venv
source venv/bin/activate
cd tts_common && pip install -r requirements.txt && cd ..
cd telegram_bot && pip install -r requirements.txt && cd ..
cd web_tts && pip install -r requirements.txt && cd ..
cd ~
cp ~/tts_projects/.env.example ~/tts_projects/.env
nano ~/tts_projects/.env
mkdir -p ~/tts_projects/telegram_bot/audio
mkdir -p ~/tts_projects/web_tts/audio
sudo cp ~/tts_projects/tts-bot.service /etc/systemd/system/
sudo cp ~/tts_projects/tts-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable tts-bot tts-web
sudo systemctl start tts-bot tts-web
```

## Проверка

```bash
sudo systemctl status tts-bot tts-web
sudo journalctl -u tts-bot -f
sudo journalctl -u tts-web -f
curl http://localhost:8001
```

## Управление

```bash
sudo systemctl restart tts-bot tts-web
sudo systemctl stop tts-bot tts-web
```

## Обновление

```bash
cd ~/tts_projects
git pull
sudo systemctl restart tts-bot tts-web
```

## Nginx (опционально)

```bash
sudo apt install nginx
sudo nano /etc/nginx/sites-available/tts-web
```

```nginx
server {
    listen 80;
    server_name your_domain_or_ip;
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/tts-web /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw enable
```
