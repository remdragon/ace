# ace
Automated Call Experience

This requires a minimum of Debian 10

NOTE: the following instructions assume http[s] access to *.debian.org, *.pythonhosted.org, *.pypi.org

```
sudo ufw allow 443
sudo apt update
sudo apt upgrade
sudo apt install -y python3-pip curl build-essential gcc make libsystemd-dev libssl-dev libffi6 libffi-dev
sudo curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
sudo pip3 install --upgrade cython
sudo pip3 install flask types-flask pyopenssl python-pam Flask-Login Flask-Session tornado systemd accept-types tzlocal
sudo pip3 install service_identity --force --upgrade
sudo python3 route_manager.py install

mkdir /usr/src/itas
cd /usr/src/itas
git clone https://github.com/remdragon/ace.git
cd ace
chmod +x ace.py
./ace.py install
./ace.py start


to enable TTS (text to speech) do the following additional setup steps:

(TODO - Josh will document this)
```
