Operations
==========

CI Backend Deployment
_____________________

You first need a functional Mesos_ cluster equipped with Ochothon_ (please refer to their respective documentations
for details).

The *YAML definition* to use for each component can be found in the repository (grep for *marathon.yml*). Please note
some of them specify settings that are not defaulted (especially for the slaves which require a few credentials and
the Slack_ relay). You can copy them all in one place and edit them according to your needs.

Go ahead and add all those pods in an arbitrary "ci" namespace (for instance). We first need a Redis_ pod in
that namespace to act as a buffer & queue. We then need at least one *hook* pod (to receive HTTP POST requests from Git)
and a at least one *slave* pod. Finally we need to add a top-level HAProxy_ to direct traffic to the hooks and a Slack_
relay to forward notifications.

Open the CLI and deploy. For instance:

.. code:: bash

    $ cd images/marathon
    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > deploy -n ci hook/marathon.yml
    my-cluster > deploy -n ci redis/marathon.yml
    my-cluster > deploy -n ci haproxy/marathon.yml
    my-cluster > deploy -n ci slack-relay/marathon.yml
    my-cluster > deploy -n ci slave/marathon.yml

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
    ci.haproxy                  |  1/1  |
    ci.slack-relay              |  1/1  |
    ci.slave                    |  1/1  |

Note the *haproxy* URL (and make sure it is reachable from your Git deployment). The container will bind to its host's
TCP 9000. For instance:

.. code:: bash

    $ ocho cli my-cluster
    welcome to the ocho CLI ! (CTRL-C or exit to get out)
    my-cluster > port 9000
    1 pods, 100% replies ->

    pod                   |  pod IP        |  public IP  |  TCP
                          |                |             |
    ci-backend.haproxy #0 |  10.50.85.97   |             |  9000

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
.. _Slack: https://slack.com/


