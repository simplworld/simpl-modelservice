'''

The business module of the modelservice `aws_profiler` django management command

'''

import boto3
from django.conf import settings


def _aws_auth():
    retval = {}

    aws_id = getattr(settings, 'PROFILER_AWS_KEY', None)
    aws_sec = getattr(settings, 'PROFILER_AWS_SEC', None)

    retval['region_name'] = getattr(settings, 'PROFILER_AWS_REGION', 'us-east-2')

    if aws_id and aws_sec:
        retval['aws_access_key_id'] = aws_id
        retval['aws_secret_access_key'] = aws_sec

    return retval


def _connect():
    retval = boto3.resource(service_name='ec2', **_aws_auth())
    return retval


def _profiler_instances():
    mc = _connect()
    retval = mc.instances.filter(
        Filters=[
            {'Name': 'tag:Environment', 'Values': ['modelservice-profiler']}
        ]
    )

    return retval


def status():
    '''
    return status information for modelservice profiler instances
    '''
    status = ['']

    for inst in _profiler_instances():
        inst_state = inst.state.get('Name', 'unknown')
        status.append(f'{inst.id}: {inst_state} -- type: {inst.instance_type} -- ip address: {inst.public_ip_address}')
    return status


def start():
    '''
    send instance start request and return status
    '''

    instances = _profiler_instances()

    results = [
        inst.start() for inst in instances
        if inst.state['Name'] != 'running'
    ]

    return status()


def stop():
    '''
    send instance stop request and return status
    '''
    instances = _profiler_instances()

    results = [
        inst.stop() for inst in instances
        if inst.state['Name'] == 'running'
    ]

    return status()
