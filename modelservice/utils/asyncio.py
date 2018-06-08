import asyncio
import inspect

from functools import update_wrapper

import aiojobs


def coro(f):
    """
    Decorator to run a coroutine into the default loop and exit.

    Useful for commands, eg::

        import djclick as click
        from modelservice.utils import coro


        @click.command()
        @coro
        async def command(name, worlds, nogamesettings, reset, noinput):
            return await ...

    """
    if not inspect.iscoroutinefunction(f):
        f = asyncio.coroutine(f)

    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(f(*args, **kwargs))
    return update_wrapper(wrapper, f)


async def spawn(func, *iterables, **kwargs):
    """
    Utility function to spawn coroutines like they were threads.

    Usage::

        async def mycoro(timeout, name):
            print(name, surname)
            await asyncio.sleep(timeout)

        timeouts = range(10)
        names = ["coro-%s" % i for i in range(10)]
        await spawn(mycoro, timeouts, names)
    """
    limit = kwargs.get('limit', 100)
    close_timeout = kwargs.get('close_timeout', 0.1)
    count = len(iterables[0])
    jobs = []
    scheduler = await aiojobs.create_scheduler(close_timeout=close_timeout, limit=limit)
    for i in range(count):
        # spawn jobs
        args = [iterable[i] for iterable in iterables]
        jobs.append(await scheduler.spawn(func(*args)))

    while scheduler.active_count:
        await asyncio.sleep(0.01)

    # gracefully close spawned jobs
    results = [await job.wait() for job in jobs]
    await scheduler.close()
    return results
