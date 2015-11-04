CD
==

The model
_________

Our goal is two-fold: we want to be able to automate CD scenario involving sequencing and decision-making while
providing a convenient entry-point for doing so (typically to trigger deployments from tools such as Jenkins_).
The model is thus quite simple: let a remote client upload both scripts (plus ancillary data such as settings or
templates) to a secure proxy which in turn will let them proxy commands to the Ochothon_ portal. This is more or
less a way to automate what a real user would do via the Ochothon_ CLI interface.

Enabling CD
___________

Just deploy a **servo** container in your Mesos_ cluster and note its auto-generated secret token. For instance:

.. code:: bash

    $ ocho cli
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    10.50.85.97 > deploy servo.yml
    100% success (+1 pods)
    10.50.85.97 > poll *servo
    1 pods, 100% replies ->

    pod                |  metrics
                       |
    marathon.servo #1  |  {"token": "edAZR8atfOahd7tfPnVo3xpJX+ks6wsV", "uptime": "0.00 hours (pid 59)"}

.. note::
    Make sure this *servo* container is reachable from where you wish to trigger your CD logic.

Defining your CD
________________

Script upload
*************

In order to run your CD scripts you first need to bundle them in a TGZ archive. This archive is then sent to the
*servo* via a HTTP POST. A mandatory signature must be provided as well: the SHA1 hash of the archive has to be
passed via the *X-Signature* header. Please note the *servo* secret token must be used as the hash key.

The HTTP POST is performed as /run/*scripts* where *scripts* is a string formed by concatenating together the name
of the Python_ modules that must be executed (separate with a + character). Any module that is specified must be
included in the uploaded archive.

This use case is typically what you would run from a tool like Jenkins_. For instance you could upload and run in
order two CD scripts called *deploy.py* and *test.py* this way:

.. code:: bash

    $ tar zcf upload.tgz *
    $ HASH=$(openssl dgst -sha1 -hmac $SERVO_TOKEN upload.tgz)
    $ HASH="sha1=${HASH##* }"
    $ curl -X POST -F tgz=@upload.tgz -H -H "X-Signature:$HASH" http://10.120.11.80:5000/run/deploy.py+test.py

.. note::
    You can include other files in the TGZ such as templates, YAML_ container definition files and so on.

Uploading from the CLI
**********************

The Ochothon_ CLI also allows you to directly upload & trigger your CD scripts in one go. The *servo* pod exposes a
dedicated *run* tool that will upload the archive and perform the SHA1 signature automatically. For instance:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > exec *servo --force run ~/my-scripts deploy.py test.py

Encryption
**********

A common use case is to deploy containers and have to specify sensitive information such as API keys and the like.
This data can be scrambled and then decrypted by the servo upon upload (especially if it is meant to be stored in a
git repository). Any file with a **.aes** extension will be assumed to be encrypted using **AES 256 CBC** and the
*servo* secret token.

.. note::
    Upon successful decryption the *.aes* extension is removed automatically, e.g *foo.yml.aes* will be made available
    to the script as *foo.yml* (exactly as if it had been uploaded in clear).

Scripting
*********

A *servo* package is available at execution time and will give you access to a *proxy* method. This method will
transparently forward CLI commands to the local Ochothon_ portal. For instance you could run the following script
to list all your containers :

.. code:: python

    from servo import servo

    if __name__ == '__main__':

        with servo(verbose=True) as proxy:
            js = proxy('ls')
            print js.keys()

You can run anything you would do via the CLI. The proxy method will request a JSON_ output when talking to
Ochothon_. You can use the resulting payload to implement complex operations. For instance you could find out where
your *web* containers are located and issue a HTTP */ping* query to make sure they are all up:

.. code:: python

    import requests
    from servo import servo

    if __name__ == '__main__':
        with servo(verbose=True) as proxy:
            js = proxy('port 80 %s.web' % prefix)
            urls = ['http://%s:%s/ping' % (details['ip'], details['ports']) for _, details in js.items()]

            for url in urls:
                get = requests.get(url)
                code = get.status_code
                assert code < 300, 'GET %s -> HTTP %d' % (url, code)

Anything printed out on the standard output will be returned back to the caller. If you HTTP POST to the *servo* and
specify *application/json* as the accepted content type the result code will always be HTTP 200 and the payload be
serialized JSON_. If you accept *text/plain* the result code will be HTTP 412 in case of failure or 200 otherwise.

.. _Docker: https://www.docker.com/
.. _Jenkins: https://jenkins-ci.org/
.. _JSON: http://www.json.org/
.. _Mesos: http://mesos.apache.org/
.. _Ochothon: https://github.com/autodesk-cloud/ochothon
.. _Python: https://www.python.org/
.. _SBT: http://www.scala-sbt.org/
.. _YAML: http://yaml.org/
