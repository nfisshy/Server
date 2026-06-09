# Raspberry Client

Client Python nhe cho Raspberry Pi. Lan dau mo app se hien onboarding toan man hinh de dang ky Raspberry va cap PIN vinh vien. Sau do app chi hien 2 phan trang: danh ba va lich su cuoc tro chuyen. Tien trinh nen `background_listener.py` luon ket noi WebSocket de nghe cuoc goi. Khi co `incoming_call`, listener se tu mo GUI, GUI hien man hinh cuoc goi toan man hinh va phat nhac chuong.

Server mac dinh:

```text
http://172.20.10.3:3000
```

## Cai dat tren Raspberry Pi

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-tk python3-opencv mpv

cd pi_client
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json
python app.py
```

Lan dau chay, app hien trang onboarding. Bam **Register And Create PIN**. Ung dung se hien PIN 6 so. PIN nay gan voi Raspberry trong suot vong doi thiet bi va khong het han. Nhap PIN nay tren app mobile de pair. Sau khi register thanh cong, app tu dong cai va khoi dong background listener. Nguoi dung khong can mo terminal de chay listener thu cong.

Neu Raspberry da register tu truoc va chi muon cai lai listener bang dung moi truong Python hien tai:

```bash
cd pi_client
source /duong/dan/toi/myenv/bin/activate
python enable_background.py
```

## Chay listener nen giong app dien thoai

Sau khi da register va da co `state.json`, binh thuong app da tu bat listener. Neu muon test thu cong:

```bash
cd pi_client
source .venv/bin/activate
python background_listener.py
```

Listener nay se:

- Ket noi WebSocket toi Main Server.
- Gui heartbeat moi 30 giay.
- Lang nghe `incoming_call` khi GUI chua mo.
- Khi co cuoc goi, ghi `pending_call.json`, tu mo `app.py`, va GUI phat nhac chuong.
- Neu khong bam dong y/tu choi trong 60 giay, app tu ngat cuoc goi.
- Tam dung socket nen trong luc GUI dang xu ly cuoc goi de tranh 2 socket cung device tranh mapping tren server.

## Test cuoc goi den khi chua co app dien thoai

Dung script `test_incoming_call.py` de tao mobile gia, pair bang PIN cua Raspberry, roi bat dau cuoc goi mobile -> Raspberry.

Dieu kien:

- Main Server dang chay.
- Raspberry da register va listener dang online.
- Ban co PIN cua Raspberry tren man hinh onboarding/home.

Chay:

```bash
cd pi_client
source .venv/bin/activate
python test_incoming_call.py --pin 123456
```

Neu server khong phai IP mac dinh:

```bash
python test_incoming_call.py --server http://172.20.10.3:3000 --pin 123456
```

Sau lenh nay, Raspberry phai tu mo man hinh cuoc goi va phat chuong.

## Chay tu dong khi Raspberry khoi dong

App se tu tao service user:

```text
~/.config/systemd/user/blind-assist-listener.service
```

va chay:

```bash
systemctl --user enable blind-assist-listener.service
systemctl --user restart blind-assist-listener.service
```

Neu systemd user khong kha dung, app se fallback sang desktop autostart:

```text
~/.config/autostart/blind-assist-listener.desktop
```

Kiem tra service user:

```bash
systemctl --user status blind-assist-listener.service
```

De service user co the chay ngay sau boot truoc khi mo terminal, Raspberry nen bat auto-login desktop. Neu muon chay ca khi user chua login, can enable linger mot lan:

```bash
sudo loginctl enable-linger $USER
```

Sua file `raspberry-client.service`, thay duong dan `/home/pi/raspberry-client` thanh duong dan thuc te cua `pi_client` neu can, sau do:

```bash
sudo cp raspberry-client.service /etc/systemd/system/raspberry-client.service
sudo systemctl daemon-reload
sudo systemctl enable raspberry-client
sudo systemctl start raspberry-client
```

Xem log:

```bash
journalctl -u raspberry-client -f
```

Luu y quan trong: de tu mo GUI Tkinter khi co cuoc goi, Raspberry phai dang co desktop/display. Neu chay headless khong co man hinh, listener van nghe duoc tin hieu goi den, nhung khong the hien giao dien.

## Toi uu toc do

- Camera duoc mo bang OpenCV `cv2.VideoCapture(0)`, giong code test da chay duoc tren Raspberry.
- Moi chunk mac dinh gom 15 frame JPEG, 640x480, sample 15 FPS.
- Khi dong y cuoc goi, app hien camera truc tiep trong trang call full-screen va gui video chunk lien tuc len Main Server.
- Phat video tu Server B bang `mpv`, tranh render trong Tkinter.
- WebSocket chay thread rieng, GUI chi nhan event qua queue nen khong bi dung.
- Listener nen giu ket noi khi GUI tat, giup Raspberry van nhan duoc cuoc goi den.

Neu Server A can MP4 thay vi H264 raw, doi `capture_command` trong `config.json` sang pipeline phu hop voi may cua ban.
