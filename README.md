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

## Environment variables 

- *GUEST_LOGLEVEL* adjust guest process logging, defaults to info
- *CROSSBAR_LOGLEVEL* adjust crossbar process logging, defaults to info

## Profiling

### Writing tasks

The profiler will run any method that starts with `profile_` one or more times against a different number of workers.

Keep in mind that, unlike unit tests, profile tasks are not isolated.

#### Measuring

The `modelservice.utils.instruments` contains classes for measuring execution times. Check the module's docstrings for details.

#### Collecting results

You can collect the result of the task by calling the `.publish_stat()` method:

```
    async def profile_random(self):
        with Timer() as timer:
            some_value = random.random()
        self.publish_stat('<unique stat name>', timer.elapsed, fmt='Average result was {stats.mean:.3f}')
```

The `fmt` string will receive an `instruments.StatAggregator` instance called `stats`. 
This object will collect the value from all workers that ran the task and will provide the following properties:

* `.min`: The lowest collected value
* `.max`: The highest collected value
* `.total`: The sum of the collected values
* `.count`: The number of collected values

Additionally, functions from the [`statistics` module](https://docs.python.org/3/library/statistics.html) 
are aliased as properties (ie: `.mean`, `.stdev`, etc.).

### Running the profiler anonymously

1. Run the `simpl-games-api` server. 
1. From a model service directory, run its server.
1. From the same model service directory, call `profile.sh`. You can use `profile.sh -h` for a list of options.

Some example anonymous profiling tasks are defined in `modelservice/profiles`. These tasks are run
unless you use the `-m` option to specify a different module path.

To run from a model service directory when logged into an AWS instance, 
call `aws_profile.sh`. You can use `aws_profile.sh -h` for a list of options.

### Running the profiler with users

You can have workers that publish and call on WAMP as specific users. Using the `.call()` or `.publish()` methods, 
it can call or publish as the user associated with that worker. 

You have the profiler spawn workers as specific users by passing a file with their emails using the `-u` option.

You will also need to use the `-m` option to specify your task's module path (e.g `my_task_module_path`).

Assuming you have a file called `myusers.txt` with the following content:

```text
s1@mysim.edu
s2@mysim.edu
s3@mysim.edu
```

You can then call:

```bash
$ profile.sh -m my_task_module_path -u myusers.txt
```

This will spawn 3 workers, each one set up to `.call` and `.publish` as one of those users.

To run from a model service directory when logged into an AWS instance, call:
 ```bash
$ aws_profile.sh -m my_task_module_path -u myusers.txt
```

Both `profile.sh` and `aws_profile.sh` invoke the `profile` management command.


Copyright © 2018 The Wharton School,  The University of Pennsylvania 

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
