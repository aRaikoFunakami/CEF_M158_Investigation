# 計測用の環境を用意する: Xvfb、openbox、テストページ配信(8000)、WebSocket エコー(8001)。冪等。
export DISPLAY=:1
pgrep -x Xvfb >/dev/null || { nohup Xvfb :1 -screen 0 1920x1080x24 > /root/fp/xvfb.log 2>&1 & sleep 2; }
pgrep -x openbox >/dev/null || { nohup openbox > /root/fp/openbox.log 2>&1 & }
pgrep -f "http.server 8000" >/dev/null || { cd /root/fp/tools/site && nohup python3 -m http.server 8000 --bind 127.0.0.1 > /root/fp/http.log 2>&1 & }
pgrep -f wsecho.py >/dev/null || { nohup python3 /root/fp/tools/wsecho.py > /root/fp/wsecho.log 2>&1 & }
sleep 2; pgrep -a -x Xvfb | cut -c1-60; pgrep -af "http.server|wsecho" | cut -c1-80
