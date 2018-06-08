# Map child resource to parent resource by name
# Although the Simpl model relationships constitute a directed acyclic graph,
# the Simpl framework enforces a tree relationship among model instances.
# Specifically, each scenario instance has a single parent instance.
SCOPE_PARENT_GRAPH = {
    'result': ('period',),
    'decision': ('period',),
    'period': ('scenario',),
    'scenario': ('world', 'runuser',),  # parent is either a world or a runuser
    'world': ('run',),
    'runuser': ('run',),
    'run': ('game',),
    'phase': ('game',),
    'role': ('game',),
}

# Specify fast filtering attributes of scopes
SCOPE_FILTER_ATTRIBUTES = {
    'result': ('period',),
    'decision': ('period',),
    'period': ('scenario',),
    'scenario': ('world', 'runuser',),
    'world': ('run',),
    'runuser': ('run', 'world'),
    'run': ('game',),
    'phase': ('game',),
    'role': ('game',),
}
