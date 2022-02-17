# EMAIL SETUP

`sudo nano /usr/share/freeswitch/scripts/eximcompat.sh`
```
#!/bin/bash
exec exim4 -t
```

`sudo chmod +x /usr/share/freeswitch/scripts/eximcompat.sh`

`sudo nano /etc/freeswitch/autoload_configs/switch.conf.xml`
```
<param name="mailer-app" value="/usr/share/freeswitch/scripts/eximcompat.sh"/>
<!--param name="mailer-app-args" value="-t" /--> <!-- make sure this is commented out -->
<param name="dump-cores" value="yes"/> <!-- optional -->
```

`sudo apt-get update`
`sudo apt-get install exim4-daemon-light`
`sudo dpkg-reconfigure exim4-config`
```
localhost
127.0.0.1
(blank)
(blank)
SMTP.EXAMPLE.COM
no
no
/var/mail
yes
root
```

`sudo nano /etc/exim4/passwd.client`
```
smtpserver:SMTPUSER:SMTPPASSWORD
```

`sudo nano /etc/email-addresses`
```
root:FROM@EXAMPLE.COM
```

Prepare for testing by running this in a separate shell:
```
tail -f /var/log/exim4/mainlog
```

Test:
```
exim -v RCPT@EXAMPLE.COM
From: FROM@EXAMPLE.COM
Subject: Test From Exim4

I Like Pie!
```
Press Ctrl+D

Troubleshooting not receiving emails
```
tail -f /varl/og/exim4/mainlog
exinext EXAMPLE.COM
exinext USER@EXAMPLE.COM
exinet MESSAGE_ID
```
