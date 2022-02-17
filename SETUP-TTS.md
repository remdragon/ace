# Text To Speech

to enable TTS (text to speech) do the following additional setup steps:

```
sudo pip3 install boto3
mkdir /var/lib/freeswitch/tts
chown freeswitch:freeswitch /var/lib/freeswitch/tts
cp -r resources/aws_tts/* `python3 -c 'import site; print(site.getsitepackages()[0])'`
chmod +rx /etc/itas/ace
cp resources/aws_tts/aws.ini.example /etc/itas/ace/aws.ini
```

**NOTE**: You will also need to add the mod_python3 module to the `/etc/freeswitch/autoload_configs/modules.conf.xml` file. You can then run the command `fs_cli -x 'reload mod_python3'`.

Modify **/etc/itas/ace/aws.ini** and modify the `aws_access_key` and `aws_secret_key` parameters with credentials from your AWS instance

To create an AWS access key and secret, log into the AWS administration console and browse to **Services >> Security, Identity, & Compliance >> IAM**

Next, browse to **User Groups** then click **Create Group**.

**Create a name** for you group, then scroll down to the **attach permissions policies** section, then in the **filter** text field enter _polly_, then press enter. Select the checkbox next to _AmazonPollyReadOnlyAccess_ policy, then click **Create Group**.

Next, browse to **Users** then click **Add users**.

**Enter a username** to create, check the _Access key - Programmatic access_ checkbox for the credential type, then click **Next: Permissions**. Select the **checkbox** next to the group you created previously, then click **Next: Tags**. Click **Next: Review**. Finally, click **Create User**.

Once the user has been created, add the _Access key ID_ and _Secret access key_ to **/etc/itas/ace/aws.ini**

To test if text to speech is working you can run the following command

```
fs_cli -x 'python streamtext voice=Joanna|text=This is a test, please disregard'
```

This command should return the location of a wav file.
