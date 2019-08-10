# Simpl Modelservice

Python Library to implement Simulations, built on Crossbar.io and Django.

[![Build Status](https://travis-ci.com/simplworld/simpl-modelservice.svg?token=cyqpBgqLC1o8qUptfcpE&branch=master)](https://travis-ci.com/simplworld/simpl-modelservice)

## Installation

### Django 2.2

```bash
$ pip install simpl-modelservice
```

### Django 1.11

```bash
$ pip install "simpl-modelservice<0.8.0"
```

## Setup development environment

    $ git clone git@github.com:simplworld/simpl-modelservice.git
    $ cd simpl-modelservice
    $ mkvirtualenv simpl-modelservice
    $ pip install -r dev-requirements.txt
    $ pip install -e .

## Run tests

    $ python runtests.py

## Development versioning

Install `bumpversion`:

    $ pip install bumpversion

Then, to release a new version, increment the version number with:

    $ bumpversion patch

Then push to the repo:

    $ git push && git push --tags

## View current WAMP subscriptions and registrations

Point your browser to http://localhost:8080/monitor and open your javascript console

## How to run a modelservice as two separate processes

It's sometimes useful to run [crossbar](https://github.com/crossbario/crossbar/) and your own model code as separate processes. By default, `run_modelservice` runs crossbar configured to kick off the sub-process `run_guest`.  You can change this by doing these 3 simple steps:

1. Get a copy of the currently in use crossbar configuration by running `./manage.py run_modelservice --print-config`.  This will print the generated configuration file and then run normally.  Simply cut-n-paste the configuration which will be a large JSON blob just before the usual Crossbar log messages.

2. Edit the configuration to remove the entire `{"type": "guest", ...}` stanza, saved to a file.

3. Run each piece separately.  If we saved our configuration into `config.json` in the current directly this would look like:

        ./manage.py run_modelservice --config=./config.json --loglevel info --settings=simpl-calc.settings

    for the crossbar service and then:

        HOSTNAME=localhost PORT=8080 ./manage.py run_guest --settings=simpl-calc.settings

    for the modelservice itself. 

## Profiling

### Writing tasks

Profiling tasks are defined in `modelservice/profiles`.

The profiler will run any method that starts with `profile_` one or more times against a different number of workers.

Keep in mind that, unlike unit tests, profile tasks are not isolated.

#### Profile users

You can have workers that publish and call on WAMP as specific users. By using the `.call()` or `.publish()` method, it will call or publish as the user associated to that worker. To learn how to run workers associated to users, see [Running profile users](#running-profile-users).

#### Measuring

The `modelservice.utils.instruments` contains classes for measuring execution times. Check the module's docstrings for details.

#### Collecting results

You can collect the result of task by calling the `.publish_stat()` method:

```
    async def profile_random(self):
        with Timer() as timer:
            some_value = random.random()
        self.publish_stat('<unique stat name>', timer.elapsed, fmt='Average result was {stats.mean:.3f}')
```

The `fmt` string will receive an `instruments.StatAggregator` instance called `stats`. This object will collect the value from all workers that ran the task and will provide the following properties:

* `.min`: The lowest collected value
* `.max`: The highest collected value
* `.total`: The sum of the collected values
* `.count`: The number of collected values

Additionally, functions from the [`statistics` module](https://docs.python.org/3/library/statistics.html) are aliased as properties (ie: `.mean`, `.stdev`, etc.).

### Running the profiler anonymously

1. Run `simpl-games-api` and its modelservice
1. From any model, run its modelservice via `run_modelservice` or `run_guest`
1. From the same model directory, call `profile.sh`. You can use `profile.sh -h` for a list of options.

To run any model directory when logged into an AWS instance, call `aws_profile.sh`. You can use `aws_profile.sh -h` for a list of options.

#### Running profile users

You can have the profiler spawn workers as specific users by passing a file with their emails using the `-u` option.

Assuming you have a file called `myusers.txt` with the following content:

```text
s1@mysim.edu
s2@mysim.edu
s3@mysim.edu
```

You can then call:

```bash
$ profile.sh -u myusers.txt
```

And it will spawn 3 workers, each of one set up to `.call` and `.publish` as that one of those users.

To run from any model directory when logged into an AWS instance, call:
 ```bash
$ aws_profile.sh -u myusers.txt
```

Both `profile.sh` and `aws_profile.sh` invoke the `profile` management command.

#### Managing the Modelservice AWS Profiler instance

##### Django settings

  * `PROFILER_AWS_KEY`: the AWS IAM access key
  * `PROFILER_AWS_SEC`: the associated IAM secret key

##### Management commands

Management of the AWS profiler instance is performed by way of the `aws_profiler` management command.

###### status

```

:# ./manage.py aws_profiler --status

i-0733d74785931f857: stopped -- type: c5.18xlarge -- ip address: 18.216.171.181

```


###### start

```

:# ./manage.py aws_profiler --start

i-0733d74785931f857: pending -- type: c5.18xlarge -- ip address: 18.216.171.181

```


###### stop

```

:# ./manage.py aws_profiler --stop

i-0733d74785931f857: stopping -- type: c5.18xlarge -- ip address: 18.216.171.181

```

Copyright © 2018 The Wharton School,  The University of Pennsylvania 

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
