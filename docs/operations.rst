Operations
==========

CI Backend Deployment
_____________________

You first need a functional Mesos_ cluster equipped with Ochothon_ (please refer to their respective documentations
for details).

The *YAML definition* to use for each component can be found in the repository (grep for *marathon.yml*). Please note
some of them specify settings that are not defaulted (especially for the slave image which requires a few credentials).
You can copy them all in one place and edit them according to your needs.

Go ahead and add all those pods in an arbitrary "ci" namespace (for instance). We first need a Redis_ pod in
that namespace to act as a buffer & queue. Let's assume we have one already running. We then need at least one *hook*
pod (to receive HTTP POST requests from Git) and a at least one *slave* pod. Let's pick 3 slaves for the sake of
illustration.

Open the CLI and deploy. For instance:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > deploy -n ci images/marathon/hook/marathon.yml -t 120
    my-cluster > deploy -n ci images/marathon/slave/marathon.yml -t 120 -p 3

Once this is done you should have 5 pods running on your cluster:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > ls
    5 pods, 100% replies ->

    cluster                     |  ok   |  status
                                |       |
    ci.hook                     |  1/1  |
    ci.redis                    |  1/1  |
    ci.slave                    |  3/3  |

Note the *hook* URL (and make sure it is reachable from your Git deployment). The container will bind to its host's
TCP 5000. For instance:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > port 5000
    1 pods, 100% replies ->

    pod                  |  pod IP        |  public IP  |  TCP
                         |                |             |
    ci-backend.hook #0   |  10.50.85.97   |             |  5000

.. note::
    You can add a front-ending HAProxy_ if needed, for instance to run multiple *hook* pods if you need to scale. I
    suggest exposing the CI backend via HTTPS only.

Pay also attention to the *hook* auto-generated secret token. This random identifier must be used when setting up your
web-hook. For instance:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > poll *hook
    1 pods, 100% replies ->

    pod                  |  metrics
                         |
    ci-backend.hook #0   |  {"token": "2ko9rHdj/JD", "uptime": "2.0 hours (pid 9)"}

.. note::
    You can specify this token in the *hook* pod configuration if you prefer to stick with a known quantity. Not doing
    so will generate a random identifier upon the pod startup.

Scaling up
__________

You can simply scale your CI backend up by cranking the number of *hook* or *slave* up. You can do it either in the
CLI or via the Marathon_ API.

.. warning::
    Changing the number of slave pods will impact the internal hashing performed to assign repositories to specific
    slaves. After doing so it is highly probable repositories will have to be cached again on a different machine.

.. _HAProxy: http://www.haproxy.org/
.. _Marathon: https://mesosphere.github.io/marathon/
.. _Mesos: http://mesos.apache.org/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Ochothon: https://github.com/autodesk-cloud/ochothon
.. _Redis: http://redis.io/


